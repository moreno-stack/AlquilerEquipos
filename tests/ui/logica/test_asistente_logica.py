"""Lógica de interfaz del asistente: turnos, preguntas rápidas y fuentes legibles."""

from alquiler.ui.logica import asistente
from tests.ui.conftest import ClienteFalso


def _respuesta(texto, emocion="feliz"):
    return {"tipo": "respuesta", "herramienta": "ninguna", "argumento": "", "respuesta": texto,
            "emocion": emocion}


def test_conversar_devuelve_un_dict_para_la_vista(ctx_factory, datos_base):
    modelo = ClienteFalso({"tipo": "herramienta", "herramienta": "equipos_disponibles",
                           "argumento": "", "respuesta": "", "emocion": "pensativo"},
                          _respuesta("Hay 2 taladros disponibles."))
    ctx = ctx_factory("cliente", cliente_llm=modelo)
    r = asistente.conversar(ctx, [], "¿qué hay?")
    assert r == {"estado": "ok", "texto": "Hay 2 taladros disponibles.", "emocion": "feliz",
                 "fuentes": ["Catálogo de equipos disponibles"], "sugerencias": []}


def test_sugerencias_y_respuesta_rapida(ctx_factory, datos_base):
    ctx = ctx_factory("empleado")
    sugerencias = asistente.sugerencias(ctx)
    assert {"id": "vencidos", "texto": "¿Qué alquileres están vencidos?"} in sugerencias
    r = asistente.rapida(ctx, "disponibles")
    assert r["estado"] == "ok" and "TAL-001" in r["texto"]
    assert r["fuentes"] == ["Catálogo de equipos disponibles"]


def test_sin_clave(ctx_factory, datos_base):
    r = asistente.conversar(ctx_factory("admin"), [], "hola")
    assert r["estado"] == "sin_api" and r["sugerencias"]
