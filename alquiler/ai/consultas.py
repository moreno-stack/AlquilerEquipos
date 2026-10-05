"""Consultas en lenguaje natural con explicabilidad (spec §6.4).

Flujo: pregunta → (1) el modelo genera SQL + pasos → (2) validación y ejecución
de solo lectura, con un intento de corrección → (3) el modelo redacta la
respuesta directa solo a partir de las filas obtenidas.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from alquiler.ai import prompts
from alquiler.ai.llm import ClienteLLM, ErrorIA
from alquiler.ai.mantenimiento import ADVERTENCIA as ADVERTENCIA_RECOMENDADOR
from alquiler.ai.mantenimiento import recomendar_mantenimiento
from alquiler.ai.sql_seguro import ErrorSQL, ejecutar_lectura, validar_sql
from alquiler.auth import Permiso, requerir_permiso
from alquiler.errors import ReglaNegocioError
from alquiler.models import Usuario

MAX_CARACTERES = 500
ADVERTENCIA = ("Respuesta generada por IA a partir de los datos consultados: verifique el SQL "
               "y las cifras antes de tomar decisiones.")
ADVERTENCIA_PREDEFINIDA = "Consulta predefinida: SQL fijo revisado, sin intervención de la IA."
_TIPOS = ("sql", "aclaracion", "no_resoluble")


@dataclass
class RespuestaConsulta:
    estado: str  # ok | sin_datos | aclaracion | no_resoluble | sin_api | error
    pregunta: str
    respuesta: str
    pasos: list[str]
    sql: str | None = None
    columnas: list[str] = field(default_factory=list)
    filas: list[tuple] = field(default_factory=list)
    truncado: bool = False
    advertencia: str = ADVERTENCIA
    sugerencias: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- predefinidas
@dataclass(frozen=True)
class ConsultaPredefinida:
    id: str
    titulo: str
    sql: str | None  # plantilla con {hoy} e {inicio_mes}; None = usa el recomendador
    pasos: tuple[str, ...]


CONSULTAS_PREDEFINIDAS: tuple[ConsultaPredefinida, ...] = (
    ConsultaPredefinida(
        "top_equipos_mes", "Equipos más alquilados este mes",
        "SELECT e.codigo, e.nombre, COUNT(*) AS alquileres FROM alquiler a "
        "JOIN equipo e ON e.id = a.equipo_id WHERE a.estado != 'cancelado' "
        "AND a.fecha_inicio BETWEEN '{inicio_mes}' AND '{hoy}' "
        "GROUP BY e.id ORDER BY alquileres DESC, e.codigo LIMIT 10",
        ("Cuenta los alquileres no cancelados que iniciaron este mes, por equipo.",
         "Ordena de mayor a menor y muestra los 10 primeros.")),
    ConsultaPredefinida(
        "ingresos_mes", "Ingresos del mes por concepto",
        "SELECT concepto, SUM(monto) AS total FROM pago "
        "WHERE fecha BETWEEN '{inicio_mes}' AND '{hoy}' GROUP BY concepto ORDER BY total DESC",
        ("Suma los pagos registrados este mes.", "Agrupa por concepto: alquiler, mora y daños.")),
    ConsultaPredefinida(
        "alquileres_activos", "Alquileres activos y vencidos",
        "SELECT a.id, c.nombre AS cliente, e.codigo AS equipo, a.fecha_inicio, "
        "a.fecha_fin_prevista, CASE WHEN a.fecha_fin_prevista < '{hoy}' THEN 'vencido' "
        "ELSE 'al día' END AS situacion FROM alquiler a JOIN cliente c ON c.id = a.cliente_id "
        "JOIN equipo e ON e.id = a.equipo_id WHERE a.estado = 'activo' "
        "ORDER BY a.fecha_fin_prevista",
        ("Lista los alquileres en estado activo.",
         "Marca como vencidos los que superaron la fecha de devolución prevista.")),
    ConsultaPredefinida(
        "clientes_retrasos", "Clientes con más devoluciones tardías",
        "SELECT c.nombre AS cliente, COUNT(*) AS devoluciones, "
        "SUM(d.dias_retraso > 0) AS con_retraso, ROUND(AVG(d.dias_retraso), 1) AS dias_promedio "
        "FROM devolucion d JOIN alquiler a ON a.id = d.alquiler_id "
        "JOIN cliente c ON c.id = a.cliente_id GROUP BY c.id HAVING con_retraso > 0 "
        "ORDER BY con_retraso DESC, dias_promedio DESC LIMIT 10",
        ("Agrupa las devoluciones por cliente.",
         "Cuenta las que tuvieron días de retraso y el promedio de días.")),
    ConsultaPredefinida(
        "equipos_a_revisar", "Equipos que deberían revisarse pronto", None,
        ("Usa el recomendador de mantenimiento preventivo (usos, días desde el servicio, "
         "uso reciente y fallas).", "Muestra los equipos con puntaje ≥ 50.")),
    ConsultaPredefinida(
        "equipos_por_estado", "Equipos por estado",
        "SELECT estado, COUNT(*) AS equipos FROM equipo GROUP BY estado ORDER BY equipos DESC",
        ("Cuenta los equipos según su estado actual.",)),
)
_POR_ID = {c.id: c for c in CONSULTAS_PREDEFINIDAS}


def sql_predefinida(consulta: ConsultaPredefinida, hoy: date) -> str:
    return consulta.sql.format(hoy=hoy.isoformat(), inicio_mes=hoy.replace(day=1).isoformat())


def ejecutar_predefinida(session: Session, actor: Usuario, id_: str, db_path: Path,
                         hoy: date | None = None) -> RespuestaConsulta:
    requerir_permiso(actor, Permiso.IA_CONSULTAS)
    hoy = hoy or date.today()
    consulta = _POR_ID.get(id_)
    if consulta is None:
        raise ReglaNegocioError("La consulta predefinida no existe.")
    if consulta.sql is None:
        alertas = recomendar_mantenimiento(session, actor, hoy=hoy, persistir=False)
        columnas = ["codigo", "puntaje", "prioridad", "confianza", "resumen"]
        filas = [(r.indicadores["codigo"], r.valor, r.indicadores["prioridad"],
                  r.confianza.value, r.resumen) for r in alertas]
        sql, truncado, advertencia = None, False, ADVERTENCIA_RECOMENDADOR
    else:
        sql = sql_predefinida(consulta, hoy)
        r = ejecutar_lectura(db_path, sql)
        columnas, filas, truncado, advertencia = r.columnas, r.filas, r.truncado, ADVERTENCIA_PREDEFINIDA
    return RespuestaConsulta(
        estado="ok" if filas else "sin_datos",
        pregunta=consulta.titulo,
        respuesta=f"{len(filas)} registros." if filas else "No hay registros para esta consulta.",
        pasos=list(consulta.pasos),
        sql=sql,
        columnas=columnas,
        filas=filas,
        truncado=truncado,
        advertencia=advertencia,
    )


# ---------------------------------------------------------------- lenguaje natural
@dataclass(frozen=True)
class _Generacion:
    tipo: str
    sql: str
    pasos: list[str]
    mensaje: str
    sugerencias: list[str]


def _es_lista_de_textos(valor) -> bool:
    return isinstance(valor, list) and all(isinstance(v, str) for v in valor)


def _interpretar(raw: dict) -> _Generacion:
    """Valida la forma del JSON del modelo; cualquier desvío es un ErrorIA."""
    try:
        g = _Generacion(raw["tipo"], raw["sql"], raw["pasos"], raw["mensaje"], raw["sugerencias"])
    except (KeyError, TypeError):
        g = None
    valido = (
        g is not None and g.tipo in _TIPOS and isinstance(g.sql, str)
        and isinstance(g.mensaje, str) and _es_lista_de_textos(g.pasos)
        and _es_lista_de_textos(g.sugerencias) and (g.tipo != "sql" or g.sql.strip())
    )
    if not valido:
        raise ErrorIA("La IA devolvió una respuesta con formato inesperado.")
    return g


def _validar_pregunta(pregunta: str | None) -> str:
    pregunta = (pregunta or "").strip()
    if not pregunta:
        raise ReglaNegocioError("Escriba una pregunta.")
    if len(pregunta) > MAX_CARACTERES:
        raise ReglaNegocioError(f"La pregunta es demasiado larga (máximo {MAX_CARACTERES} caracteres).")
    return pregunta


def consultar(session: Session, actor: Usuario, pregunta: str, cliente: ClienteLLM | None,
              db_path: Path, hoy: date | None = None) -> RespuestaConsulta:
    requerir_permiso(actor, Permiso.IA_CONSULTAS)
    pregunta = _validar_pregunta(pregunta)
    hoy = hoy or date.today()
    if cliente is None:
        return RespuestaConsulta(
            estado="sin_api", pregunta=pregunta, pasos=[], advertencia="",
            respuesta="La IA no está configurada (falta GROQ_API_KEY en alquiler.env o en el "
                      "entorno). Puede usar las consultas predefinidas.",
            sugerencias=[c.titulo for c in CONSULTAS_PREDEFINIDAS],
        )

    sistema = prompts.prompt_generacion(hoy)
    mensajes = [{"role": "user", "content": pregunta}]
    try:
        for intento in (1, 2):
            raw = cliente.generar_json(sistema, mensajes, prompts.ESQUEMA_GENERACION)
            g = _interpretar(raw)
            if g.tipo != "sql":
                return RespuestaConsulta(estado=g.tipo, pregunta=pregunta, respuesta=g.mensaje,
                                         pasos=g.pasos, sugerencias=g.sugerencias)
            try:
                sql = validar_sql(g.sql)
                resultado = ejecutar_lectura(db_path, sql)
                break
            except ErrorSQL as e:
                if intento == 2:
                    return RespuestaConsulta(
                        estado="error", pregunta=pregunta, pasos=g.pasos, sql=g.sql,
                        respuesta=f"No fue posible obtener una consulta válida: {e}",
                    )
                mensajes = mensajes + [
                    {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
                    {"role": "user", "content": f"La consulta fue rechazada o falló: {e} "
                                                "Corrígela respetando todas las restricciones."},
                ]

        if not resultado.filas:
            return RespuestaConsulta(
                estado="sin_datos", pregunta=pregunta, pasos=g.pasos, sql=sql,
                columnas=resultado.columnas,
                respuesta="La consulta se ejecutó correctamente pero no devolvió registros.",
                sugerencias=["Pruebe ampliando el período o revisando los filtros de la pregunta."],
            )

        redaccion = cliente.generar_json(
            prompts.prompt_respuesta(),
            [{"role": "user", "content": prompts.mensaje_respuesta(
                pregunta, sql, resultado.columnas, resultado.filas, resultado.truncado)}],
            prompts.ESQUEMA_RESPUESTA,
        )
        texto = redaccion.get("respuesta")
        if not isinstance(texto, str) or not texto.strip():
            raise ErrorIA("La IA devolvió una respuesta con formato inesperado.")
    except ErrorIA as e:
        return RespuestaConsulta(estado="error", pregunta=pregunta, respuesta=str(e), pasos=[])

    advertencia = ADVERTENCIA
    if resultado.truncado:
        advertencia += (f" El resultado fue truncado a {len(resultado.filas)} filas; "
                        "la respuesta se basa en una muestra.")
    return RespuestaConsulta(
        estado="ok", pregunta=pregunta, respuesta=texto.strip(), pasos=g.pasos, sql=sql,
        columnas=resultado.columnas, filas=resultado.filas, truncado=resultado.truncado,
        advertencia=advertencia,
    )
