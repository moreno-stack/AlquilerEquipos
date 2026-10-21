"""Lógica de interfaz del asistente "Cubi": convierte sus respuestas en datos simples para la vista."""

from alquiler.ai import asistente as cubi
from alquiler.ui.logica.contexto import Contexto

FUENTES = {
    "equipos_disponibles": "Catálogo de equipos disponibles",
    "mis_alquileres": "Tu historial de alquileres",
    "resumen_negocio": "Resumen del negocio de hoy",
    "alquileres_vencidos": "Alquileres vencidos",
    "riesgo_mantenimiento": "Estimación de mantenimiento (IA local)",
    "retrasos": "Análisis de retrasos (IA local)",
    "demanda": "Predicción de demanda (IA local)",
    "ingresos_mes": "Reporte de ingresos del mes",
    "consulta_libre": "Consulta SQL de solo lectura",
}


def _sugerencias(actor) -> list[dict]:
    return [{"id": s.id, "texto": s.texto} for s in cubi.sugerencias_para(actor)]


def _dict(r: cubi.RespuestaAsistente, actor) -> dict:
    por_texto = {s["texto"]: s for s in _sugerencias(actor)}
    return {
        "estado": r.estado, "texto": r.texto, "emocion": r.emocion,
        "fuentes": [FUENTES.get(h, h) for h in dict.fromkeys(r.herramientas)],
        "sugerencias": [por_texto[t] for t in r.sugerencias if t in por_texto],
    }


def sugerencias(ctx: Contexto) -> list[dict]:
    return ctx.ejecutar(lambda s, a: _sugerencias(a))


def conversar(ctx: Contexto, historial: list[dict], texto: str) -> dict:
    """Un turno; ``historial`` = [{"rol": "usuario"|"asistente", "texto": ...}] (sin el actual)."""
    return ctx.ejecutar(lambda s, a: _dict(cubi.conversar(
        s, a, historial, texto, ctx.cliente_llm, ctx.config.db_path, hoy=ctx.hoy()), a))


def rapida(ctx: Contexto, id_: str) -> dict:
    return ctx.ejecutar(lambda s, a: _dict(cubi.respuesta_rapida(s, a, id_, ctx.hoy()), a))
