"""Análisis IA (tarjetas explicables) y Consola IA (lenguaje natural en segundo plano)."""

import threading

import pytest
from sqlalchemy import select

from alquiler.ai.llm import ErrorIA
from alquiler.ai.resultado import Resultado
from alquiler.models import Equipo, Nivel
from alquiler.ui import trabajador
from alquiler.ui.logica import ia
from alquiler.ui.vistas.consola_ia import VistaConsolaIA
from alquiler.ui.vistas.ia import VistaAnalisisIA
from tests.ui.conftest import ClienteFalso

SQL = "SELECT codigo, nombre FROM equipo ORDER BY codigo"
PASOS = ["Consulto la tabla equipo.", "Ordeno por código."]


def gen(sql=SQL, tipo="sql", mensaje="", sugerencias=()):
    return {"tipo": tipo, "sql": sql, "pasos": PASOS if tipo == "sql" else [],
            "mensaje": mensaje, "sugerencias": list(sugerencias)}


class ClienteLento(ClienteFalso):
    """Se bloquea en cada llamada hasta que la prueba lo libera."""

    def __init__(self, *respuestas):
        super().__init__(*respuestas)
        self.liberar = threading.Event()

    def generar_json(self, *args):
        self.liberar.wait(5)
        return super().generar_json(*args)


def _esperar(qtbot, vista):
    qtbot.waitUntil(lambda: not vista.ocupado, timeout=5000)


# ---------------------------------------------------------------- lógica
def test_tarjeta_conserva_explicacion():
    r = Resultado(resumen="TAL-001: ≈80/100", valor=80.0, confianza=Nivel.MEDIA,
                  indicadores={"usos_desde_servicio": 25, "aporte_puntos": {"usos": 35.0},
                               "prioridad": "alta"},
                  justificacion=["Usos 25/20 → 35 pts"], advertencia="Estimación basada en…")
    t = ia.tarjeta(r)
    assert (t["resumen"], t["confianza"], t["justificacion"], t["advertencia"]) == (
        "TAL-001: ≈80/100", "media", ["Usos 25/20 → 35 pts"], "Estimación basada en…")
    assert ("Usos desde servicio", "25") in t["indicadores"]
    assert ("Aporte puntos", "usos: 35.0") in t["indicadores"]
    con_claves = ia.tarjeta(Resultado("r", 1.0, Nivel.ALTA, {"normalizados": {"fallas_12m": 1.0}},
                                      ["j"], "Estimación"))
    assert ("Normalizados", "fallas 12m: 1.0") in con_claves["indicadores"]
    assert t["prioridad"] == "alta"


# ---------------------------------------------------------------- análisis IA
def test_analisis_mantenimiento_muestra_tarjetas(qtbot, ctx_factory, datos_base, fabrica):
    with fabrica() as s:
        s.scalar(select(Equipo).where(Equipo.codigo == "TAL-001")).usos_acumulados = 60
        s.commit()
    v = VistaAnalisisIA(ctx_factory("empleado"))
    qtbot.addWidget(v)
    pestana = v.pestanas["mantenimiento"]
    pestana.boton.click()
    qtbot.waitUntil(pestana.boton.isEnabled, timeout=5000)
    assert len(pestana.tarjetas) == 1
    tarjeta = pestana.tarjetas[0]
    assert "TAL-001" in tarjeta.etiqueta_resumen.text()
    assert tarjeta.insignia_estimacion.text() == "Estimación"
    assert "Prioridad" in tarjeta.insignias_extra[0].text()


def test_analisis_sin_resultados_lo_dice(qtbot, ctx_factory, datos_base):
    v = VistaAnalisisIA(ctx_factory("admin"))
    qtbot.addWidget(v)
    pestana = v.pestanas["retrasos"]
    pestana.boton.click()
    qtbot.waitUntil(pestana.boton.isEnabled, timeout=5000)
    assert pestana.tarjetas == [] and "sin devoluciones" in pestana.etiqueta_estado.text().lower()


# ---------------------------------------------------------------- consola
def test_consola_respuesta_en_dos_partes(qtbot, ctx_factory, datos_base):
    falso = ClienteFalso(gen(), {"respuesta": "Hay 2 equipos: TAL-001 y TAL-002."})
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=falso))
    qtbot.addWidget(v)
    assert v.aviso_sin_api.isHidden()
    v.campo_pregunta.setText("¿Qué equipos hay?")
    v.boton_consultar.click()
    assert v.ocupado and not v.boton_consultar.isEnabled()
    _esperar(qtbot, v)
    assert v.etiqueta_respuesta.text() == "Hay 2 equipos: TAL-001 y TAL-002."   # parte 1
    assert [v.lista_pasos.item(i).text() for i in range(v.lista_pasos.count())] == [
        "1. Consulto la tabla equipo.", "2. Ordeno por código."]                  # parte 2
    assert v.tabla_datos.filas_mostradas() == 2
    assert v.texto_sql.toPlainText() == SQL and v.texto_sql.isHidden()
    assert "verifique" in v.etiqueta_advertencia.text()
    assert v.lista_historial.count() == 1 and v.boton_consultar.isEnabled()


def test_consola_historial_reabre_respuesta(qtbot, ctx_factory, datos_base):
    falso = ClienteFalso(gen(), {"respuesta": "Primera."}, gen(), {"respuesta": "Segunda."})
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=falso))
    qtbot.addWidget(v)
    for pregunta in ("uno", "dos"):
        v.campo_pregunta.setText(pregunta)
        v.boton_consultar.click()
        _esperar(qtbot, v)
    assert v.lista_historial.count() == 2 and v.etiqueta_respuesta.text() == "Segunda."
    v.lista_historial.setCurrentRow(1)  # el más antiguo queda abajo
    assert v.etiqueta_respuesta.text() == "Primera." and len(falso.llamadas) == 4


def test_consola_predefinida_sin_api(qtbot, ctx_factory, datos_base):
    v = VistaConsolaIA(ctx_factory("admin"))
    qtbot.addWidget(v)
    assert not v.aviso_sin_api.isHidden() and len(v.botones_predefinidas) == 6
    assert "GROQ_API_KEY" in v.aviso_sin_api.text() and "alquiler.env" in v.aviso_sin_api.text()
    v.botones_predefinidas["equipos_por_estado"].click()
    _esperar(qtbot, v)
    assert v.tabla_datos.filas_mostradas() == 1 and v.tabla_datos.texto(0, 0) == "Disponible"
    v.campo_pregunta.setText("¿Cuánto facturamos?")
    v.boton_consultar.click()
    _esperar(qtbot, v)
    assert v.etiqueta_estado.text() == "IA no configurada"
    assert len(v.botones_sugerencias) == 6
    v.botones_sugerencias[5].click()  # "Equipos por estado" → ejecuta la predefinida
    _esperar(qtbot, v)
    assert v.tabla_datos.filas_mostradas() == 1


def test_consola_sugerencia_clicable_rellena_pregunta(qtbot, ctx_factory, datos_base):
    falso = ClienteFalso(gen(tipo="aclaracion", sql="", mensaje="¿De qué período?",
                             sugerencias=["Ingresos de marzo de 2026"]))
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=falso))
    qtbot.addWidget(v)
    v.campo_pregunta.setText("¿Cuánto ganamos?")
    v.boton_consultar.click()
    _esperar(qtbot, v)
    assert v.etiqueta_estado.text() == "Se necesita una aclaración"
    assert v.etiqueta_respuesta.text() == "¿De qué período?"
    v.botones_sugerencias[0].click()
    assert v.campo_pregunta.text() == "Ingresos de marzo de 2026"


def test_consola_doble_enter_una_sola_consulta(qtbot, ctx_factory, datos_base):
    lento = ClienteLento(gen(), {"respuesta": "Ok."})
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=lento))
    qtbot.addWidget(v)
    v.campo_pregunta.setText("¿Qué equipos hay?")
    v.campo_pregunta.returnPressed.emit()
    v.campo_pregunta.returnPressed.emit()   # segundo Enter mientras la primera sigue en curso
    lento.liberar.set()
    _esperar(qtbot, v)
    assert len(lento.llamadas) == 2          # una consulta = generación + redacción
    assert v.lista_historial.count() == 1


def test_consola_error_ia_se_muestra_sin_romper(qtbot, ctx_factory, datos_base):
    falso = ClienteFalso(ErrorIA("Sin conexión con el servicio de IA."), gen(), {"respuesta": "Ok."})
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=falso))
    qtbot.addWidget(v)
    v.campo_pregunta.setText("¿Algo?")
    v.boton_consultar.click()
    _esperar(qtbot, v)
    assert v.etiqueta_estado.text() == "No se pudo completar la consulta"
    assert v.etiqueta_respuesta.text() == "Sin conexión con el servicio de IA."
    v.boton_consultar.click()                # se puede volver a consultar
    _esperar(qtbot, v)
    assert v.etiqueta_respuesta.text() == "Ok."


def test_consola_pregunta_vacia_no_consulta(qtbot, ctx_factory, datos_base):
    falso = ClienteFalso()
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=falso))
    qtbot.addWidget(v)
    v.boton_consultar.click()
    assert not v.ocupado and falso.llamadas == []


def test_cerrar_con_consulta_en_curso(qtbot, ctx_factory, datos_base):
    lento = ClienteLento(gen(), {"respuesta": "Tarde."})
    v = VistaConsolaIA(ctx_factory("admin", cliente_llm=lento))
    v.campo_pregunta.setText("¿Qué equipos hay?")
    v.boton_consultar.click()
    v.close()
    v.deleteLater()
    qtbot.wait(50)
    lento.liberar.set()
    assert trabajador.esperar_tareas(5000)
    qtbot.wait(100)  # el resultado llega a un widget destruido: se descarta sin error
