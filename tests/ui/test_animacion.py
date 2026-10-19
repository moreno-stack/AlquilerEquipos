"""Animaciones de la interfaz: duraciones de los tokens, apagado en pruebas y cada efecto termina en
su estado final (valor exacto, brillo restaurado, posición original)."""

import pytest
from PySide6.QtCore import QAbstractAnimation, QEvent
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QLabel,
    QProgressBar,
    QWidget,
)

from alquiler.ui import animacion, widgets


@pytest.fixture
def con_animaciones(monkeypatch):
    monkeypatch.setattr(animacion, "_forzado", True)


def _termino(anim):
    return lambda: anim.state() == QAbstractAnimation.State.Stopped


# ---------------------------------------------------------------- interruptor y duraciones
def test_duraciones_salen_de_los_tokens(con_animaciones):
    assert (animacion.duracion("rapida"), animacion.duracion("base"),
            animacion.duracion("lenta")) == (120, 200, 320)


def test_sin_pantalla_no_hay_animaciones():
    """Las pruebas corren en ``offscreen``: todo queda en su estado final al instante."""
    assert not animacion.activas()
    assert animacion.duracion("lenta") == 0


def test_variable_de_entorno_las_apaga(monkeypatch):
    monkeypatch.setattr(animacion, "_sin_pantalla", lambda: False)
    monkeypatch.delenv("ALQUILER_ANIMACIONES", raising=False)
    assert animacion.activas()
    monkeypatch.setenv("ALQUILER_ANIMACIONES", "0")
    assert not animacion.activas()


# ---------------------------------------------------------------- contador
@pytest.mark.parametrize("final, fraccion, esperado", [
    ("$ 1.250.000", 0.5, "$ 625.000"),
    ("45 %", 0, "0 %"),
    ("12", 1, "12"),
    ("3 / 8", 0.5, "2 / 8"),       # solo cuenta la primera cifra
    ("Sin datos", 0.3, "Sin datos"),
])
def test_texto_intermedio(final, fraccion, esperado):
    assert animacion.texto_intermedio(final, fraccion) == esperado


def test_contar_sin_animaciones_pone_el_valor_final(qtbot):
    etiqueta = QLabel()
    qtbot.addWidget(etiqueta)
    assert animacion.contar(etiqueta, "$ 1.250.000") is None
    assert etiqueta.text() == "$ 1.250.000"


def test_contar_con_animacion_termina_en_el_valor(qtbot, con_animaciones):
    etiqueta = QLabel()
    qtbot.addWidget(etiqueta)
    anim = animacion.contar(etiqueta, "37")
    assert etiqueta.text() == "0"
    qtbot.waitUntil(_termino(anim), timeout=3000)
    assert etiqueta.text() == "37"


# ---------------------------------------------------------------- fundido y escalonado
def test_fundido_restaura_el_brillo(qtbot, con_animaciones):
    etiqueta = QLabel("x")
    qtbot.addWidget(etiqueta)
    widgets.aplicar_brillo(etiqueta, "acento", alfa=50, radio=30)
    anim = animacion.fundido_entrada(etiqueta)
    assert isinstance(etiqueta.graphicsEffect(), QGraphicsOpacityEffect)
    qtbot.waitUntil(_termino(anim), timeout=3000)
    efecto = etiqueta.graphicsEffect()
    assert isinstance(efecto, QGraphicsDropShadowEffect)
    assert efecto.blurRadius() == 30 and efecto.color().alpha() == 50


def test_fundido_sin_efecto_previo_lo_quita_al_final(qtbot, con_animaciones):
    w = QWidget()
    qtbot.addWidget(w)
    anim = animacion.fundido_entrada(w)
    qtbot.waitUntil(_termino(anim), timeout=3000)
    assert w.graphicsEffect() is None


def test_fundido_sin_animaciones_no_toca_nada(qtbot):
    etiqueta = QLabel("x")
    qtbot.addWidget(etiqueta)
    widgets.aplicar_brillo(etiqueta)
    efecto = etiqueta.graphicsEffect()
    assert animacion.fundido_entrada(etiqueta) is None
    assert etiqueta.graphicsEffect() is efecto


def test_escalonar_entra_uno_tras_otro(qtbot, con_animaciones):
    ws = [QWidget() for _ in range(3)]
    for w in ws:
        qtbot.addWidget(w)
    grupos = animacion.escalonar(ws, paso=50)
    duraciones = [g.totalDuration() for g in grupos]
    assert duraciones == sorted(duraciones) and len(set(duraciones)) == 3
    qtbot.waitUntil(lambda: all(_termino(g)() for g in grupos), timeout=3000)


# ---------------------------------------------------------------- barras, temblor y brillo
def test_llenar_barra(qtbot, con_animaciones):
    barra = QProgressBar()
    qtbot.addWidget(barra)
    anim = animacion.llenar(barra, 70)
    assert barra.value() < 70
    qtbot.waitUntil(_termino(anim), timeout=3000)
    assert barra.value() == 70


def test_llenar_barra_sin_animaciones(qtbot):
    barra = QProgressBar()
    qtbot.addWidget(barra)
    animacion.llenar(barra, 55)
    assert barra.value() == 55


def test_temblor_vuelve_a_su_sitio(qtbot, con_animaciones):
    w = QWidget()
    qtbot.addWidget(w)
    w.move(40, 30)
    anim = animacion.temblor(w)
    qtbot.waitUntil(_termino(anim), timeout=3000)
    assert (w.x(), w.y()) == (40, 30)


def test_brillo_al_pasar_se_intensifica_y_vuelve(qtbot, con_animaciones):
    w = QLabel("x")
    qtbot.addWidget(w)
    widgets.aplicar_brillo(w, "acento", alfa=40, radio=20)
    animacion.brillo_al_pasar(w)
    QApplication.sendEvent(w, QEvent(QEvent.Type.Enter))
    qtbot.waitUntil(lambda: w.graphicsEffect().blurRadius() > 30, timeout=3000)
    QApplication.sendEvent(w, QEvent(QEvent.Type.Leave))
    qtbot.waitUntil(lambda: w.graphicsEffect().blurRadius() == 20, timeout=3000)


# ---------------------------------------------------------------- piezas del centro de control
def test_fondo_cosmico_flota(qtbot, con_animaciones):
    f = widgets.FondoCosmico()
    qtbot.addWidget(f)
    assert f.posiciones(0) != f.posiciones(2000)        # los nodos se mueven con el tiempo
    assert f.posiciones(0) == widgets.FondoCosmico().posiciones(0)  # pero de forma determinista
    f.show()
    assert f.animado()


def test_fondo_cosmico_quieto_sin_animaciones(qtbot):
    f = widgets.FondoCosmico()
    qtbot.addWidget(f)
    f.show()
    assert not f.animado()


def test_dona_gira_al_cargar(qtbot, con_animaciones):
    d = widgets.GraficoDona()
    qtbot.addWidget(d)
    d.cargar([("Disponible", 3)], "30 %", "Utilización")
    assert d.progreso < 1
    qtbot.waitUntil(lambda: d.progreso == 1, timeout=3000)


def test_dona_sin_animaciones_completa(qtbot):
    d = widgets.GraficoDona()
    qtbot.addWidget(d)
    d.cargar([("Disponible", 3)], "30 %", "Utilización")
    assert d.progreso == 1


def test_tendencia_anima_las_series(qtbot, con_animaciones):
    from PySide6.QtCharts import QChart
    g = widgets.GraficoTendencia()
    qtbot.addWidget(g)
    g.cargar(["ene"], [("Iniciados", [2], "acento")])
    assert g.chart().animationOptions() & QChart.AnimationOption.SeriesAnimations


def test_titulo_degradado(qtbot):
    t = widgets.TextoDegradado("Alquiler de Equipos")
    qtbot.addWidget(t)
    assert t.text() == "Alquiler de Equipos"
    assert not t.grab().isNull()
