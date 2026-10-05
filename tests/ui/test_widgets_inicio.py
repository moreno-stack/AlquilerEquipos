"""Piezas de la pantalla de Inicio: tarjeta KPI navegable y barra de estados de la flota."""

from PySide6.QtCore import Qt

from alquiler.ui.tema import COLOR_ESTADO
from alquiler.ui.widgets import BarraEstados, TarjetaKPI

DATOS = {"clave": "activos", "titulo": "Alquileres activos", "valor": "12",
         "detalle": "3 vencidos", "tono": "info", "destino": "alquileres"}


def test_tarjeta_textos(qtbot):
    t = TarjetaKPI(DATOS)
    qtbot.addWidget(t)
    assert (t.etiqueta_titulo.text(), t.etiqueta_valor.text(), t.etiqueta_detalle.text()) == (
        "Alquileres activos", "12", "3 vencidos")
    assert t.objectName() == "tarjetaKpi" and t.destino == "alquileres"
    assert t.property("navegable") is True
    assert t.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_tarjeta_emite_destino(qtbot):
    t = TarjetaKPI(DATOS)
    qtbot.addWidget(t)
    with qtbot.waitSignal(t.activada, timeout=500) as senal:
        qtbot.mouseClick(t, Qt.MouseButton.LeftButton)
    assert senal.args == ["alquileres"]


def test_tarjeta_sin_destino_no_emite(qtbot):
    t = TarjetaKPI({**DATOS, "destino": None, "detalle": ""})
    qtbot.addWidget(t)
    recibidas = []
    t.activada.connect(recibidas.append)
    qtbot.mouseClick(t, Qt.MouseButton.LeftButton)
    assert recibidas == [] and t.property("navegable") is False
    assert t.etiqueta_detalle.isHidden()


def test_barra_segmentos(qtbot):
    b = BarraEstados()
    qtbot.addWidget(b)
    b.cargar([("Disponible", 3), ("Alquilado", 0), ("Reservado", 1)])
    assert b.segmentos() == [("Disponible", 3, COLOR_ESTADO["Disponible"][0]),
                             ("Reservado", 1, COLOR_ESTADO["Reservado"][0])]
    assert b.texto_leyenda() == "Disponible 3 · Alquilado 0 · Reservado 1"
    assert COLOR_ESTADO["Reservado"][0] in b.leyenda.text()  # cada estado con su color
    assert not b.etiqueta_vacia.isVisibleTo(b)


def test_barra_vacia(qtbot):
    b = BarraEstados()
    qtbot.addWidget(b)
    b.cargar([("Disponible", 0), ("Alquilado", 0)])
    assert b.segmentos() == []
    assert b.etiqueta_vacia.isVisibleTo(b)
    assert b.etiqueta_vacia.text() == "Sin equipos registrados"


def test_barra_pinta_sin_error(qtbot):
    b = BarraEstados()
    qtbot.addWidget(b)
    b.resize(400, 80)
    b.cargar([(estado, i + 1) for i, estado in enumerate(COLOR_ESTADO)])
    assert not b.grab().isNull()
    b.cargar([])
    assert not b.grab().isNull()
