"""Configuración: variables de entorno y, opcionalmente, el archivo ``alquiler.env``.

El archivo existe para que el usuario "agregue la API al final" sin tocar las
variables de entorno de Windows: copia ``alquiler.env.ejemplo`` como
``alquiler.env`` y pega su clave de Groq. Una variable de entorno con valor
siempre gana sobre el archivo.
"""

import os
import sys
import warnings
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal

# Verificado el 2026-10-04 en console.groq.com/docs/models y /docs/structured-outputs:
# modelo de producción con salida JSON estricta (json_schema strict) y alta velocidad.
MODELO_POR_DEFECTO = "openai/gpt-oss-20b"
NOMBRE_ARCHIVO_ENV = "alquiler.env"
_PREFIJOS_ACEPTADOS = ("GROQ_", "ALQUILER_")


def _carpetas_env() -> tuple[Path, ...]:
    if getattr(sys, "frozen", False):  # ejecutable de PyInstaller
        programa = Path(sys.executable).resolve().parent
    else:  # desde el código: raíz del proyecto
        programa = Path(__file__).resolve().parent.parent
    return programa, Path.home() / ".alquiler_equipos"


_CARPETAS_ENV: tuple[Path, ...] = _carpetas_env()


@dataclass(frozen=True, repr=False)
class Config:
    db_path: Path
    admin_password: str
    factor_mora: float
    groq_api_key: str | None
    groq_model: str
    groq_timeout: float
    groq_max_retries: int
    origen_clave: str | None = None  # "entorno", "archivo" o None

    def __repr__(self) -> str:
        partes = []
        for campo in fields(self):
            valor = getattr(self, campo.name)
            if campo.name in ("groq_api_key", "admin_password") and valor:
                valor = "…" + valor[-4:]
            partes.append(f"{campo.name}={valor!r}")
        return f"Config({', '.join(partes)})"


# ---------------------------------------------------------------- archivo alquiler.env
def _texto_del_archivo(ruta: Path) -> str | None:
    """UTF-8 (con o sin BOM) y, si falla, ANSI de Windows (cp1252, Bloc de notas antiguo)."""
    try:
        crudo = ruta.read_bytes()
    except OSError as e:
        warnings.warn(f"{ruta.name}: no se pudo leer ({e.strerror or e}); se ignora.", stacklevel=3)
        return None
    try:
        return crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return crudo.decode("cp1252", errors="replace")


def leer_archivo_env(ruta: Path) -> dict[str, str]:
    """Lee ``CLAVE=valor`` por línea; tolera BOM, CRLF, ANSI, comentarios y comillas.

    Nunca lanza: un archivo ilegible o una línea mal escrita solo producen un aviso (que no
    repite el contenido de la línea, porque podría ser la clave pegada sin ``GROQ_API_KEY=``).
    """
    texto = _texto_del_archivo(ruta)
    datos: dict[str, str] = {}
    for numero, linea in enumerate((texto or "").splitlines(), 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if "=" not in linea:
            warnings.warn(f"{ruta.name}, línea {numero} ignorada: falta '=' "
                          "(formato esperado CLAVE=valor).", stacklevel=2)
            continue
        clave, valor = (parte.strip() for parte in linea.split("=", 1))
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1].strip()
        elif " #" in valor or "\t#" in valor:  # comentario al final de una línea sin comillas
            valor = valor.replace("\t#", " #").split(" #", 1)[0].strip()
        if clave.startswith(_PREFIJOS_ACEPTADOS):
            datos[clave] = valor
    return datos


def buscar_archivo_env() -> Path | None:
    for carpeta in _CARPETAS_ENV:
        ruta = carpeta / NOMBRE_ARCHIVO_ENV
        if ruta.is_file():
            return ruta
    return None


# ---------------------------------------------------------------- validaciones
def _texto_opcional(valor: str | None) -> str | None:
    if valor is None or not valor.strip():
        return None
    return valor.strip()


def _factor_mora(valor: str) -> float:
    try:
        factor = float(valor.strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"ALQUILER_FACTOR_MORA debe ser un número, se recibió {valor!r}") from None
    if factor <= 0:
        raise ValueError(f"ALQUILER_FACTOR_MORA debe ser mayor que 0, se recibió {valor!r}")
    return factor


def _timeout(valor: str) -> float:
    try:
        segundos = float(valor.strip().replace(",", "."))
    except ValueError:
        raise ValueError(f"GROQ_TIMEOUT debe ser un número de segundos, se recibió {valor!r}") from None
    if segundos <= 0:
        raise ValueError(f"GROQ_TIMEOUT debe ser mayor que 0, se recibió {valor!r}")
    return segundos


def _reintentos(valor: str) -> int:
    try:
        n = int(valor.strip())
    except ValueError:
        raise ValueError(f"GROQ_MAX_RETRIES debe ser un entero, se recibió {valor!r}") from None
    if not 0 <= n <= 10:
        raise ValueError(f"GROQ_MAX_RETRIES debe estar entre 0 y 10, se recibió {valor!r}")
    return n


def cargar_config(env: Mapping[str, str] | None = None,
                  archivo: Path | None | Literal[False] = None) -> Config:
    """``archivo``: ``None`` lo busca en las carpetas habituales; ``False`` no usa ninguno."""
    env = os.environ if env is None else env
    if archivo is None:
        archivo = buscar_archivo_env()
    del_archivo = leer_archivo_env(archivo) if archivo and archivo.exists() else {}
    del_entorno = {k: v for k, v in env.items() if v and v.strip()}
    valores = {**del_archivo, **del_entorno}

    clave = _texto_opcional(valores.get("GROQ_API_KEY"))
    origen = None
    if clave:
        origen = "entorno" if "GROQ_API_KEY" in del_entorno else "archivo"
    db_path = valores.get("ALQUILER_DB_PATH") or Path.home() / ".alquiler_equipos" / "alquiler.db"
    return Config(
        db_path=Path(db_path).expanduser(),
        admin_password=valores.get("ALQUILER_ADMIN_PASSWORD") or "admin1234",
        factor_mora=_factor_mora(valores.get("ALQUILER_FACTOR_MORA", "1.5")),
        groq_api_key=clave,
        groq_model=_texto_opcional(valores.get("GROQ_MODEL")) or MODELO_POR_DEFECTO,
        groq_timeout=_timeout(valores.get("GROQ_TIMEOUT", "30")),
        groq_max_retries=_reintentos(valores.get("GROQ_MAX_RETRIES", "2")),
        origen_clave=origen,
    )
