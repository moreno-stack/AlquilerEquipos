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
