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


def test_enlaces_de_la_red(qtbot):
    f = widgets.FondoCosmico()
    qtbot.addWidget(f)
    enlaces = f.enlaces(1000, 600)
    assert enlaces and all(0 <= i < j < len(f.nodos()) for i, j in enlaces)
    assert enlaces == f.enlaces(1000, 600)  # siempre la misma red


def test_sin_pulsos_por_defecto(qtbot):
    f = widgets.FondoCosmico()
    qtbot.addWidget(f)
    assert f.pulsos_en(1234, 1000, 600) == []


def test_pulsos_recorren_enlaces_reales(qtbot):
    f = widgets.FondoCosmico(pulsos=6)
    qtbot.addWidget(f)
    enlaces = set(f.enlaces(1000, 600))
    for t in (0, 700, 5000, 123456):
        pulsos = f.pulsos_en(t, 1000, 600)
        assert len(pulsos) == 6
        for origen, destino, avance in pulsos:
            assert (min(origen, destino), max(origen, destino)) in enlaces
            assert 0 <= avance < 1
    assert f.pulsos_en(5000, 1000, 600) == widgets.FondoCosmico(pulsos=6).pulsos_en(5000, 1000, 600)
    assert f.pulsos_en(5000, 1000, 600) != f.pulsos_en(5600, 1000, 600)  # se mueven


def test_pulsos_se_pintan_y_cambian_el_dibujo(qtbot):
    con, sin = widgets.FondoCosmico(pulsos=6), widgets.FondoCosmico()
    for f in (con, sin):
        qtbot.addWidget(f)
        f.resize(800, 500)
        f._t = 900
    assert con.grab().toImage() != sin.grab().toImage()


def test_nodo_de_llegada_se_enciende(qtbot):
    f = widgets.FondoCosmico(pulsos=1)
    qtbot.addWidget(f)
    _, destino, _ = f.pulsos_en(0, 1000, 600)[0]
    llegando = 0.95 * 1600  # avance 0,95 del primer viaje
    assert f.encendido(destino, llegando, 1000, 600) > 0.5
    assert f.encendido(destino, 100, 1000, 600) == 0  # el pulso aún va lejos
