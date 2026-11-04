"""Indicadores de carga: barra neón que recorre y texto con puntos animados."""

import pytest

from alquiler.ui import animacion, widgets


@pytest.fixture
def con_animaciones(monkeypatch):
    monkeypatch.setattr(animacion, "_forzado", True)


def test_barra_de_carga_oculta_hasta_iniciar(qtbot):
    b = widgets.BarraCarga()
    qtbot.addWidget(b)
    assert not b.activa() and b.isHidden()
    b.iniciar()
    assert b.activa() and not b.isHidden()
    b.detener()
    assert not b.activa() and b.isHidden()


def test_barra_de_carga_recorre(qtbot, con_animaciones):
    b = widgets.BarraCarga()
    qtbot.addWidget(b)
    b.resize(400, 3)
    b.iniciar()
    inicial = b.posicion
    qtbot.waitUntil(lambda: b.posicion != inicial, timeout=2000)
    assert not b.grab().isNull()


def test_texto_cargando_sin_animaciones_es_fijo(qtbot):
    t = widgets.TextoCargando()
    qtbot.addWidget(t)
    t.iniciar("Analizando")
    assert t.text() == "Analizando…"
    t.detener("Listo")
    assert t.text() == "Listo"


def test_texto_cargando_con_puntos_animados(qtbot, con_animaciones):
    t = widgets.TextoCargando()
    qtbot.addWidget(t)
    t.iniciar("Analizando")
    vistos = set()
    qtbot.waitUntil(lambda: vistos.add(t.text()) or len(vistos) >= 3, timeout=3000)
    assert all(v.startswith("Analizando") for v in vistos)
    t.detener("")
    assert t.text() == "" and not t.animado()
