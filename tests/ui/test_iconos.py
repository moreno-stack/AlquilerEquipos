"""Iconos vectoriales del menú lateral (dibujados en código, sin archivos externos)."""

import pytest
from PySide6.QtGui import QIcon

from alquiler.ui import iconos
from alquiler.ui.logica.navegacion import SECCIONES
from alquiler.ui.ventana import VentanaPrincipal


def test_cada_seccion_tiene_icono():
    assert {s.clave for s in SECCIONES} <= set(iconos.SVG)
    assert "salir" in iconos.SVG


@pytest.mark.parametrize("nombre", sorted(iconos.SVG))
def test_icono_se_dibuja(qapp, nombre):
    icono = iconos.icono(nombre, "#94A3B8", "#020617")
    normal = icono.pixmap(20, 20, QIcon.Mode.Normal).toImage()
    seleccionado = icono.pixmap(20, 20, QIcon.Mode.Selected).toImage()
    opacos = [(x, y) for x in range(20) for y in range(20) if normal.pixelColor(x, y).alpha() > 128]
    assert opacos, "el icono quedó vacío"
    x, y = opacos[0]
    assert normal.pixelColor(x, y).name() != seleccionado.pixelColor(x, y).name()  # cambia de color


def test_icono_desconocido_falla_claro():
    with pytest.raises(KeyError):
        iconos.icono("no-existe", "#FFFFFF")


def test_menu_lateral_con_iconos(qtbot, ctx_factory):
    v = VentanaPrincipal(ctx_factory("admin"), {})
    qtbot.addWidget(v)
    assert all(not v.lista.item(i).icon().isNull() for i in range(v.lista.count()))
    assert not v.boton_cerrar_sesion.icon().isNull()
