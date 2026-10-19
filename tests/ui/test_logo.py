"""Logo "cubo neural": cubo de alambre neón con nodos en los vértices y un núcleo de IA al centro."""

import pytest
from PySide6.QtGui import QColor

from alquiler.ui import animacion, logo, widgets


def test_geometria_del_cubo():
    vertices = logo.vertices()
    assert len(vertices) == 8 and len(set(vertices)) == 8          # 8 vértices distintos
    assert all(0.05 <= x <= 0.95 and 0.05 <= y <= 0.95 for x, y in vertices)  # dentro del lienzo
    aristas = logo.aristas()
    assert len(aristas) == 12
    assert sum(1 for _, _, oculta in aristas if oculta) == 3        # las 3 del vértice trasero
    nx, ny = logo.nucleo()
    assert 0.4 < nx < 0.6 and 0.4 < ny < 0.6                        # el núcleo va al centro


@pytest.mark.parametrize("lado", [16, 32, 64, 256])
def test_se_dibuja_a_cualquier_tamano(qapp, lado):
    imagen = logo.pixmap_logo(lado).toImage()
    assert (imagen.width(), imagen.height()) == (lado, lado)
    assert imagen.pixelColor(0, 0).alpha() == 0                      # fondo transparente
    opacos = sum(1 for x in range(lado) for y in range(lado) if imagen.pixelColor(x, y).alpha() > 128)
    assert opacos > lado                                             # hay trazo visible


def test_usa_colores_de_marca(qapp):
    imagen = logo.pixmap_logo(128).toImage()
    nx, ny = logo.nucleo()
    centro = QColor(imagen.pixelColor(int(nx * 128), int(ny * 128)))
    assert centro.alpha() > 200 and centro.lightness() > 150         # núcleo encendido


def test_icono_de_la_aplicacion(qapp):
    tamanos = {s.width() for s in logo.icono_app().availableSizes()}
    assert {16, 32, 256} <= tamanos


def test_widget_late_con_animaciones(qtbot, monkeypatch):
    monkeypatch.setattr(animacion, "_forzado", True)
    w = logo.Logo(64)
    qtbot.addWidget(w)
    w.show()
    assert w.animado()
    qtbot.waitUntil(lambda: w.latido < 0.9, timeout=3000)


def test_widget_quieto_sin_animaciones(qtbot):
    w = logo.Logo(64)
    qtbot.addWidget(w)
    w.show()
    assert not w.animado() and w.latido == 1.0
    assert (w.width(), w.height()) == (64, 64) and not w.grab().isNull()


def test_la_marca_lleva_el_logo(qtbot):
    m = widgets.marca("Alquiler de Equipos")
    qtbot.addWidget(m)
    assert m.findChild(logo.Logo) is not None


def test_ventanas_con_el_icono(qtbot, fabrica, config, ctx_factory):
    from alquiler.ui.login import LoginDialog
    from alquiler.ui.ventana import VentanaPrincipal
    dlg = LoginDialog(fabrica, config, None, lambda: None)
    v = VentanaPrincipal(ctx_factory("admin"), {})
    for w in (dlg, v):
        qtbot.addWidget(w)
        assert not w.windowIcon().isNull()
    assert dlg.findChild(logo.Logo) is not None                      # la portada lo muestra grande
