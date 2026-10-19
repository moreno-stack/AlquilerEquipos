"""Piezas del centro de control: fondo cósmico, paneles de vidrio, brillo neón y gráficos."""

from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel

from alquiler.ui import widgets
from alquiler.ui.tema import COLOR_ESTADO


def test_fondo_cosmico_es_determinista_y_se_pinta(qtbot):
    a, b = widgets.FondoCosmico(), widgets.FondoCosmico()
    for f in (a, b):
        qtbot.addWidget(f)
        f.resize(800, 500)
    assert len(a.nodos()) >= 30
    assert a.nodos() == b.nodos()  # misma semilla: el fondo no "salta" entre sesiones
    assert not a.grab().isNull()


def test_panel_de_vidrio(qtbot):
    p = widgets.Panel("Tendencia de alquileres", "Últimos 6 meses")
    qtbot.addWidget(p)
    assert p.objectName() == "panelVidrio"
    assert (p.etiqueta_titulo.text(), p.etiqueta_subtitulo.text()) == (
        "Tendencia de alquileres", "Últimos 6 meses")
    p.capa.addWidget(QLabel("contenido"))


def test_brillo_neon(qtbot):
    etiqueta = QLabel("x")
    qtbot.addWidget(etiqueta)
    widgets.aplicar_brillo(etiqueta, "purpura_neon")
    efecto = etiqueta.graphicsEffect()
    assert isinstance(efecto, QGraphicsDropShadowEffect)
    assert efecto.blurRadius() >= 20 and efecto.color().alpha() < 255


def test_dona_segmentos_y_centro(qtbot):
    d = widgets.GraficoDona()
    qtbot.addWidget(d)
    d.resize(220, 220)
    d.cargar([("Disponible", 6), ("Alquilado", 0), ("Reservado", 2)], "40 %", "Utilización")
    assert d.segmentos() == [("Disponible", 6, COLOR_ESTADO["Disponible"][0]),
                             ("Reservado", 2, COLOR_ESTADO["Reservado"][0])]
    assert (d.texto_centro, d.subtexto_centro) == ("40 %", "Utilización")
    assert not d.grab().isNull()


def test_dona_vacia(qtbot):
    d = widgets.GraficoDona()
    qtbot.addWidget(d)
    d.cargar([("Disponible", 0)], "0 %", "Utilización")
    assert d.segmentos() == [] and d.vacia()
    assert not d.grab().isNull()


def test_grafico_tendencia(qtbot):
    g = widgets.GraficoTendencia()
    qtbot.addWidget(g)
    g.cargar(["ene", "feb", "mar"], [("Iniciados", [3, 5, 2], "acento"),
                                     ("Devueltos", [1, 4, 6], "purpura_neon")])
    assert g.categorias() == ["ene", "feb", "mar"]
    assert g.series_datos() == [("Iniciados", [3, 5, 2]), ("Devueltos", [1, 4, 6])]
    g.cargar(["ene"], [("Iniciados", [0], "acento")])  # recargar reemplaza, no acumula
    assert g.series_datos() == [("Iniciados", [0])]


def test_tarjeta_kpi_con_icono(qtbot):
    t = widgets.TarjetaKPI({"titulo": "Vencidos", "valor": "1", "tono": "peligro", "destino": None,
                            "icono": "alerta"})
    qtbot.addWidget(t)
    assert t.etiqueta_icono is not None and not t.etiqueta_icono.pixmap().isNull()
