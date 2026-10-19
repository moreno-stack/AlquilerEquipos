"""Portada de ingreso: fondo cósmico, marca con degradado, beneficios y panel de vidrio con el login."""

import pytest
from PySide6.QtCore import QAbstractAnimation
from PySide6.QtWidgets import QDialog, QGraphicsOpacityEffect

from alquiler.auth import crear_usuario
from alquiler.models import Rol
from alquiler.ui import animacion, widgets
from alquiler.ui.login import LoginDialog
from tests.ui.conftest import HOY


@pytest.fixture
def portada(qtbot, fabrica, config):
    with fabrica() as s:
        crear_usuario(s, "luis", "clave-segura", Rol.EMPLEADO, "Luis Gómez")
    dlg = LoginDialog(fabrica, config, None, lambda: HOY)
    qtbot.addWidget(dlg)
    return dlg


def test_estructura_de_la_portada(portada):
    assert isinstance(portada.fondo, widgets.FondoCosmico)
    assert isinstance(portada.titulo, widgets.TextoDegradado)
    assert "Alquiler de Equipos" in portada.titulo.text()
    assert len(portada.beneficios) == 3 and all(b.text() for b in portada.beneficios)
    assert portada.panel.objectName() == "panelVidrio"
    assert portada.boton_ingresar.text() == "INGRESAR"
    assert portada.minimumWidth() >= 960 and portada.minimumHeight() >= 600


def test_campos_con_icono(portada):
    assert portada.campo_usuario.actions() and portada.campo_password.actions()
    assert portada.campo_usuario.placeholderText() and portada.campo_password.placeholderText()


def test_login_correcto_sigue_igual(portada):
    portada.campo_usuario.setText("luis")
    portada.campo_password.setText("clave-segura")
    portada.boton_ingresar.click()
    assert portada.result() == QDialog.DialogCode.Accepted
    assert portada.contexto.usuario.username == "luis"


def test_error_hace_temblar_el_panel(portada, monkeypatch, qtbot):
    monkeypatch.setattr(animacion, "_forzado", True)
    portada.show()
    portada.campo_usuario.setText("luis")
    portada.campo_password.setText("mala")
    portada.boton_ingresar.click()
    assert "incorrectos" in portada.etiqueta_error.text()
    anim = portada.animacion_error
    assert anim is not None
    qtbot.waitUntil(lambda: anim.state() == QAbstractAnimation.State.Stopped, timeout=3000)


def test_entrada_animada_al_mostrarse(portada, monkeypatch):
    monkeypatch.setattr(animacion, "_forzado", True)
    portada.show()
    assert isinstance(portada.panel.graphicsEffect(), QGraphicsOpacityEffect)
