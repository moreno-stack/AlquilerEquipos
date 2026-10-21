"""Asistente "Cubi": herramientas de solo lectura por rol, conversación con el modelo (falso) y
respuestas rápidas sin clave de IA."""

from datetime import date

import pytest

from alquiler.ai import asistente as cubi
from alquiler.ai.llm import ErrorIA
from alquiler.errors import ReglaNegocioError
from alquiler.models import Cliente, EstadoAlquiler, EstadoEquipo, Pago, ConceptoPago, MetodoPago
from tests.ai.conftest import HOY
from tests.services.conftest import nuevo_alquiler


class ModeloFalso:
    """Devuelve respuestas guionadas y registra lo que recibió."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def generar_json(self, sistema, mensajes, esquema):
        self.llamadas.append({"sistema": sistema, "mensajes": list(mensajes), "esquema": esquema})
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def herramienta(nombre, argumento=""):
    return {"tipo": "herramienta", "herramienta": nombre, "argumento": argumento,
            "respuesta": "", "emocion": "pensativo"}


def responder(texto, emocion="feliz"):
    return {"tipo": "respuesta", "herramienta": "ninguna", "argumento": "", "respuesta": texto,
            "emocion": emocion}


def _conversar(session, actor, modelo, texto="hola", historial=None, db_path=None):
    return cubi.conversar(session, actor, historial or [], texto, modelo, db_path, hoy=HOY)


# ---------------------------------------------------------------- herramientas por rol
def test_cada_rol_ve_solo_sus_herramientas(admin, empleado, usuario_cliente):
    nombres = lambda u: {h.nombre for h in cubi.herramientas_para(u)}  # noqa: E731
    assert nombres(usuario_cliente) == {"equipos_disponibles", "mis_alquileres"}
    assert {"resumen_negocio", "alquileres_vencidos", "riesgo_mantenimiento"} <= nombres(empleado)
    assert not {"ingresos_mes", "consulta_libre", "mis_alquileres"} & nombres(empleado)
    assert {"ingresos_mes", "consulta_libre"} <= nombres(admin)


def test_equipos_disponibles_filtra(session, usuario_cliente, equipo, categoria):
    from alquiler.models import Equipo
    session.add(Equipo(codigo="TAL-002", nombre="Taladro inalámbrico", categoria=categoria,
                       tarifa_diaria=30_000, fecha_adquisicion=date(2025, 1, 1),
                       estado=EstadoEquipo.ALQUILADO))
    session.commit()
    datos = cubi.ejecutar_herramienta(session, usuario_cliente, "equipos_disponibles", "", HOY, None)
    assert [e["codigo"] for e in datos["equipos"]] == ["TAL-001"]
    assert datos["equipos"][0]["tarifa_diaria"] == "$25.000"


def test_mis_alquileres_solo_los_propios(session, usuario_cliente, cliente, equipo):
    otro = Cliente(documento="99", nombre="Otro", telefono="1")
    session.add(otro)
    session.commit()
    nuevo_alquiler(session, cliente, equipo)
    nuevo_alquiler(session, otro, equipo, estado=EstadoAlquiler.FINALIZADO)
    datos = cubi.ejecutar_herramienta(session, usuario_cliente, "mis_alquileres", "", HOY, None)
    assert len(datos["alquileres"]) == 1 and datos["alquileres"][0]["equipo"] == "TAL-001"


def test_cliente_no_puede_usar_herramientas_del_personal(session, usuario_cliente):
    with pytest.raises(ReglaNegocioError, match="no está disponible"):
        cubi.ejecutar_herramienta(session, usuario_cliente, "resumen_negocio", "", HOY, None)


def test_herramienta_desconocida(session, admin):
    with pytest.raises(ReglaNegocioError, match="no está disponible"):
        cubi.ejecutar_herramienta(session, admin, "borrar_todo", "", HOY, None)


def test_resumen_y_vencidos(session, empleado, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo, inicio=date(2026, 3, 1), fin=date(2026, 3, 5))
    resumen = cubi.ejecutar_herramienta(session, empleado, "resumen_negocio", "", HOY, None)
    assert resumen["alquileres_activos"] == 1 and resumen["vencidos"] == 1
    vencidos = cubi.ejecutar_herramienta(session, empleado, "alquileres_vencidos", "", HOY, None)
    assert vencidos["alquileres"][0] == {"cliente": "Ana Pérez", "equipo": "TAL-001",
                                         "fecha_prevista": "2026-03-05", "dias_vencido": 5}


def test_ingresos_del_mes(session, admin, cliente, equipo):
    alquiler = nuevo_alquiler(session, cliente, equipo)
    session.add(Pago(alquiler=alquiler, monto=50_000, fecha=date(2026, 3, 2),
                     concepto=ConceptoPago.ALQUILER, metodo=MetodoPago.EFECTIVO))
    session.commit()
    datos = cubi.ejecutar_herramienta(session, admin, "ingresos_mes", "", HOY, None)
    assert datos["total"] == "$50.000"


# ---------------------------------------------------------------- conversación con el modelo
def test_respuesta_directa(session, usuario_cliente):
    modelo = ModeloFalso(responder("Hola, soy Cubi. ¿En qué te ayudo?"))
    r = _conversar(session, usuario_cliente, modelo)
    assert (r.estado, r.texto, r.emocion, r.herramientas) == (
        "ok", "Hola, soy Cubi. ¿En qué te ayudo?", "feliz", [])
    sistema = modelo.llamadas[0]["sistema"]
    assert "Cubi" in sistema and "equipos_disponibles" in sistema
    assert "resumen_negocio" not in sistema  # al cliente no se le ofrece lo del personal


def test_usa_una_herramienta_y_responde(session, usuario_cliente, equipo):
    modelo = ModeloFalso(herramienta("equipos_disponibles", "taladro"),
                         responder("Hay 1 taladro disponible: TAL-001."))
    r = _conversar(session, usuario_cliente, modelo, "¿hay taladros?")
    assert r.texto == "Hay 1 taladro disponible: TAL-001."
    assert r.herramientas == ["equipos_disponibles"]
    segundo = modelo.llamadas[1]["mensajes"][-1]["content"]
    assert "TAL-001" in segundo  # el modelo recibe los datos reales para redactar


def test_herramienta_no_permitida_se_informa_al_modelo(session, usuario_cliente):
    modelo = ModeloFalso(herramienta("ingresos_mes"),
                         responder("Esa información es solo para el personal.", "neutral"))
    r = _conversar(session, usuario_cliente, modelo)
    assert r.estado == "ok" and r.herramientas == []
    assert "no está disponible" in modelo.llamadas[1]["mensajes"][-1]["content"]


def test_limite_de_pasos(session, empleado):
    modelo = ModeloFalso(*[herramienta("resumen_negocio")] * 5)
    r = _conversar(session, empleado, modelo)
    assert r.estado == "error" and len(modelo.llamadas) == cubi.MAX_PASOS + 1


def test_historial_se_envia_recortado(session, usuario_cliente):
    historial = [{"rol": "usuario" if i % 2 == 0 else "asistente", "texto": f"m{i}"}
                 for i in range(30)]
    modelo = ModeloFalso(responder("ok"))
    _conversar(session, usuario_cliente, modelo, "nueva", historial=historial)
    mensajes = modelo.llamadas[0]["mensajes"]
    assert len(mensajes) == cubi.MAX_HISTORIAL + 1
    assert mensajes[-1] == {"role": "user", "content": "nueva"}
    assert mensajes[-2] == {"role": "assistant", "content": "m29"}


def test_error_de_la_ia_se_explica(session, usuario_cliente):
    r = _conversar(session, usuario_cliente, ModeloFalso(ErrorIA("Sin conexión con Groq.")))
    assert (r.estado, r.emocion) == ("error", "confundido") and "Sin conexión" in r.texto


def test_respuesta_con_formato_raro(session, usuario_cliente):
    r = _conversar(session, usuario_cliente, ModeloFalso({"tipo": "otra cosa"}))
    assert r.estado == "error"


@pytest.mark.parametrize("texto", ["", "   ", "x" * (cubi.MAX_CARACTERES + 1)])
def test_mensaje_invalido(session, usuario_cliente, texto):
    with pytest.raises(ReglaNegocioError):
        _conversar(session, usuario_cliente, ModeloFalso(), texto)


def test_sin_clave_ofrece_las_preguntas_rapidas(session, empleado):
    r = cubi.conversar(session, empleado, [], "hola", None, None, hoy=HOY)
    assert r.estado == "sin_api" and r.sugerencias == [s.texto for s in cubi.sugerencias_para(empleado)]


# ---------------------------------------------------------------- preguntas rápidas (sin IA)
def test_sugerencias_por_rol(admin, empleado, usuario_cliente):
    ids = lambda u: [s.id for s in cubi.sugerencias_para(u)]  # noqa: E731
    assert "mis_alquileres" in ids(usuario_cliente) and "vencidos" not in ids(usuario_cliente)
    assert "vencidos" in ids(empleado) and "ingresos" not in ids(empleado)
    assert "ingresos" in ids(admin)


def test_pregunta_rapida_responde_localmente(session, empleado, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo, inicio=date(2026, 3, 1), fin=date(2026, 3, 5))
    r = cubi.respuesta_rapida(session, empleado, "vencidos", HOY)
    assert r.estado == "ok" and "Ana Pérez" in r.texto and "TAL-001" in r.texto
    assert r.herramientas == ["alquileres_vencidos"]


def test_pregunta_rapida_ajena_al_rol(session, usuario_cliente):
    with pytest.raises(ReglaNegocioError):
        cubi.respuesta_rapida(session, usuario_cliente, "ingresos", HOY)


def test_textos_en_singular_y_plural():
    assert cubi.plural(1, "alquiler vencido", "alquileres vencidos") == "1 alquiler vencido"
    assert cubi.plural(3, "equipo", "equipos") == "3 equipos"
    texto, _ = cubi._redactar("vencidos", {"total": 1, "alquileres": [
        {"cliente": "Ana", "equipo": "T-1", "dias_vencido": 1, "fecha_prevista": "x"}]})
    assert texto.startswith("Hay 1 alquiler vencido:") and "1 día de retraso" in texto
