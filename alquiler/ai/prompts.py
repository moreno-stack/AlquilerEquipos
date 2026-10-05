"""Prompts del Text-to-SQL: esquema inyectado, reglas de negocio y protocolo (spec §6.4).

El esquema se genera desde ``Base.metadata`` para que nunca se desincronice de
los modelos; las tablas vetadas no aparecen.
"""

from datetime import date

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, Float, Integer, MetaData, String, Text

import alquiler.models  # noqa: F401  (registra las tablas)
from alquiler.db import Base

TABLAS_EXCLUIDAS = frozenset({"usuario", "alembic_version"})
MAX_FILAS_AL_MODELO = 50


def _tipo(columna) -> str:
    t = columna.type
    if isinstance(t, Enum):
        return "TEXT valores: " + "|".join(f"'{v}'" for v in t.enums)
    for clase, nombre in ((Boolean, "BOOLEAN(0/1)"), (DateTime, "DATETIME"), (Date, "DATE"),
                          (Integer, "INTEGER"), (Float, "REAL"), (JSON, "JSON"),
                          (Text, "TEXT"), (String, "TEXT")):
        if isinstance(t, clase):
            return nombre
    return str(t)


def describir_esquema(metadata: MetaData = Base.metadata) -> str:
    lineas = []
    for nombre in sorted(metadata.tables):
        if nombre in TABLAS_EXCLUIDAS:
            continue
        columnas = []
        for c in metadata.tables[nombre].columns:
            partes = [c.name, _tipo(c)]
            if c.primary_key:
                partes.append("PK")
            for fk in c.foreign_keys:
                if fk.column.table.name not in TABLAS_EXCLUIDAS:
                    partes.append(f"FK→{fk.column.table.name}.{fk.column.name}")
            columnas.append(" ".join(partes))
        lineas.append(f"{nombre}({', '.join(columnas)})")
    return "\n".join(lineas)


def prompt_generacion(hoy: date) -> str:
    return f"""Eres el asistente de consultas de un sistema de alquiler de equipos. Conviertes
preguntas en español en UNA consulta SQLite de solo lectura sobre este esquema:

{describir_esquema()}

Reglas de negocio:
- Hoy es {hoy.isoformat()}. Usa esa fecha literal; no uses date('now').
- Los montos son pesos colombianos (COP) enteros, sin decimales.
- Las fechas DATE son texto ISO 'AAAA-MM-DD'. "Este mes" = el mes de hoy.
- Un alquiler en curso tiene estado 'activo'; uno vencido es 'activo' con fecha_fin_prevista < hoy.
- Los ingresos son la suma de pago.monto (conceptos: 'alquiler', 'mora', 'danos').
- La mora cobrada en una devolución está en devolucion.recargo_mora; el retraso en devolucion.dias_retraso.
- Una falla de un equipo es un mantenimiento de tipo 'correctivo'.
- Los alquileres con estado 'cancelado' no cuentan como uso ni como demanda.

Restricciones:
- Genera solo SELECT (o WITH … SELECT): una única sentencia, sin punto y coma intermedios.
- Nunca consultes usuarios del sistema ni contraseñas.
- Usa los nombres exactos de tablas y columnas. Muestra datos legibles (codigo, nombre)
  además de los id. Para "los N más…" usa ORDER BY y LIMIT.
- No inventes tablas, columnas ni datos.

Protocolo de respuesta (JSON):
- tipo "sql": sql con la consulta; pasos = 2 a 5 frases en español que expliquen qué
  tablas y filtros usas y por qué, incluida cualquier suposición; mensaje = ""; sugerencias = [].
- tipo "aclaracion": solo si ninguna suposición razonable resuelve la ambigüedad;
  mensaje = la pregunta de aclaración; sugerencias = 2 o 3 reformulaciones concretas; sql = "".
- tipo "no_resoluble": si estos datos no permiten responder; mensaje = el motivo;
  sugerencias = preguntas relacionadas que sí se pueden responder; sql = "".
"""


ESQUEMA_GENERACION = {
    "type": "object",
    "properties": {
        "tipo": {"type": "string", "enum": ["sql", "aclaracion", "no_resoluble"]},
        "sql": {"type": "string"},
        "pasos": {"type": "array", "items": {"type": "string"}},
        "mensaje": {"type": "string"},
        "sugerencias": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tipo", "sql", "pasos", "mensaje", "sugerencias"],
    "additionalProperties": False,
}

ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {"respuesta": {"type": "string"}},
    "required": ["respuesta"],
    "additionalProperties": False,
}


def prompt_respuesta() -> str:
    return """Redactas la respuesta directa a la pregunta de un administrador de un negocio de
alquiler de equipos, en español, en 1 a 3 frases.
- Básate SOLO en las filas entregadas; no inventes ni extrapoles cifras.
- Si las filas son una muestra o el resultado fue truncado, dilo.
- Escribe los montos como pesos colombianos (p. ej. $1.250.000).
- No expliques el SQL: la explicación de los pasos se muestra aparte.
Responde en JSON con la clave "respuesta"."""


def _celda(valor) -> str:
    return "(vacío)" if valor is None else str(valor)


def mensaje_respuesta(pregunta: str, sql: str, columnas: list[str], filas: list[tuple],
                      truncado: bool) -> str:
    muestra = filas[:MAX_FILAS_AL_MODELO]
    tabla = "\n".join([" | ".join(columnas)] + [" | ".join(map(_celda, f)) for f in muestra])
    notas = [f"Se muestran {len(muestra)} de {len(filas)} filas."]
    if truncado:
        notas.append(f"El resultado fue truncado: hay más de {len(filas)} filas en total.")
    return (f"Pregunta: {pregunta}\n\nSQL ejecutado:\n{sql}\n\nResultado:\n{tabla}\n\n"
            + " ".join(notas))
