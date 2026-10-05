"""Validación y ejecución de solo lectura del SQL generado por la IA (spec §6.4).

Defensa en profundidad — la consulta debe superar tres barreras:
1. ``validar_sql``: análisis estático del texto (sin comentarios ni literales).
2. Conexión SQLite ``mode=ro`` + ``PRAGMA query_only=ON``.
3. ``set_authorizer``: solo lectura y nunca la tabla ``usuario``.
"""

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from alquiler.errors import ReglaNegocioError

PROHIBIDAS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX", "ANALYZE", "TRUNCATE", "BEGIN", "COMMIT", "ROLLBACK",
    "SAVEPOINT", "RELEASE",
})
IDENTIFICADORES_VETADOS = frozenset({"USUARIO", "PASSWORD_HASH", "LOAD_EXTENSION", "ALEMBIC_VERSION",
                                     "SQLITE_MASTER", "SQLITE_SCHEMA", "SQLITE_TEMP_MASTER",
                                     "SQLITE_TEMP_SCHEMA"})
# sqlite_master/sqlite_schema revelarían la estructura de "usuario" (password_hash).
TABLAS_VETADAS = frozenset({"usuario", "alembic_version", "sqlite_master", "sqlite_schema",
                            "sqlite_temp_master", "sqlite_temp_schema"})
# Una sola reserva gigante (randomblob(1e9)) no la detiene el timeout: se acota el tamaño
# de cualquier texto o blob. Ningún campo del sistema se acerca a este límite.
MAX_BYTES_VALOR = 100_000
_PALABRA = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ErrorSQL(ReglaNegocioError):
    """La consulta fue rechazada o falló al ejecutarse."""


@dataclass
class ResultadoSQL:
    columnas: list[str]
    filas: list[tuple]
    truncado: bool
    milisegundos: int


def _sin_literales(sql: str) -> str:
    """Devuelve el SQL con literales de texto y comentarios reemplazados por espacios.

    El contenido de los identificadores entre comillas dobles, corchetes o acentos
    graves se conserva sin las comillas, para que ``"usuario"`` también se detecte.
    """
    salida, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c == "-" and sql.startswith("--", i):
            fin = sql.find("\n", i)
            i = n if fin == -1 else fin
            salida.append(" ")
        elif c == "/" and sql.startswith("/*", i):
            fin = sql.find("*/", i + 2)
            i = n if fin == -1 else fin + 2
            salida.append(" ")
        elif c == "'":
            i += 1
            while i < n:
                if sql[i] == "'" and sql.startswith("''", i):
                    i += 2
                elif sql[i] == "'":
                    break
                else:
                    i += 1
            i += 1
            salida.append(" '' ")
        elif c in "\"`[":
            cierre = {"\"": "\"", "`": "`", "[": "]"}[c]
            fin = sql.find(cierre, i + 1)
            fin = n if fin == -1 else fin
            salida.append(f" {sql[i + 1:fin]} ")
            i = fin + 1
        else:
            salida.append(c)
            i += 1
    return "".join(salida)


def validar_sql(sql: str) -> str:
    """Devuelve la sentencia limpia (sin ``;`` final) o lanza ``ErrorSQL``."""
    limpio = _sin_literales(sql).strip().rstrip(";").strip()
    if not limpio:
        raise ErrorSQL("La consulta está vacía.")
    if ";" in limpio:
        raise ErrorSQL("Solo se permite una sola sentencia SQL.")
    palabras = list(_PALABRA.finditer(limpio))
    for m in palabras:  # primero lo prohibido: el motivo nombra la operación rechazada
        palabra = m.group().upper()
        if palabra == "REPLACE" and limpio[m.end():].lstrip().startswith("("):
            continue  # la función replace(texto, a, b) es de solo lectura
        if palabra in PROHIBIDAS:
            raise ErrorSQL(f"Operación no permitida en consultas de solo lectura: {palabra}.")
        if palabra in IDENTIFICADORES_VETADOS:
            raise ErrorSQL(f"Acceso no permitido a '{m.group()}'.")
    if not palabras or palabras[0].group().upper() not in ("SELECT", "WITH"):
        raise ErrorSQL("Solo se permiten consultas de lectura que empiecen por SELECT o WITH.")
    return sql.strip().rstrip(";").strip()


# ---------------------------------------------------------------- ejecución
_PERMITIDAS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
               getattr(sqlite3, "SQLITE_RECURSIVE", 33)}


def _autorizador(accion, arg1, arg2, _db, _trigger):
    if accion not in _PERMITIDAS:
        return sqlite3.SQLITE_DENY
    if accion == sqlite3.SQLITE_READ and arg1 and arg1.lower() in TABLAS_VETADAS:
        return sqlite3.SQLITE_DENY
    if accion == sqlite3.SQLITE_FUNCTION and arg2 and arg2.lower() == "load_extension":
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _ejecutar_sin_validar(db_path: Path, sql: str, limite: int, timeout_s: float) -> ResultadoSQL:
    """Ejecuta con las barreras 2 y 3. Uso interno: llamar a ``ejecutar_lectura``."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise ErrorSQL("No se encontró la base de datos.")
    # as_uri() codifica espacios y tildes (p. ej. "Nueva carpeta") correctamente.
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_BYTES_VALOR)
        conn.set_authorizer(_autorizador)
        limite_tiempo = time.monotonic() + timeout_s
        conn.set_progress_handler(lambda: int(time.monotonic() > limite_tiempo), 1000)
        inicio = time.monotonic()
        cursor = conn.execute(sql)
        filas = cursor.fetchmany(limite + 1)
        columnas = [d[0] for d in cursor.description or []]
    except sqlite3.DatabaseError as e:
        mensaje = str(e)
        if "interrupted" in mensaje:
            raise ErrorSQL(
                f"La consulta tardó demasiado (más de {timeout_s:g} s) y se canceló."
            ) from None
        if "too big" in mensaje:
            raise ErrorSQL("La consulta genera un valor demasiado grande y se canceló.") from None
        if any(s in mensaje for s in ("not authorized", "prohibited", "readonly")):
            raise ErrorSQL("Acceso no permitido por la política de solo lectura.") from None
        raise ErrorSQL(f"SQLite rechazó la consulta: {mensaje}") from None
    finally:
        conn.close()
    return ResultadoSQL(
        columnas=columnas,
        filas=[tuple(f) for f in filas[:limite]],
        truncado=len(filas) > limite,
        milisegundos=int((time.monotonic() - inicio) * 1000),
    )


def ejecutar_lectura(db_path: Path, sql: str, limite: int = 200, timeout_s: float = 3.0) -> ResultadoSQL:
    """Valida (barrera 1) y ejecuta en solo lectura (barreras 2 y 3)."""
    return _ejecutar_sin_validar(db_path, validar_sql(sql), limite, timeout_s)
