"""Vistas de clientes, usuarios y perfil."""

import pytest

from alquiler.auth import crear_usuario
from alquiler.models import Rol
from alquiler.ui import widgets
from alquiler.ui.logica.contexto import iniciar_sesion
from alquiler.ui.vistas.clientes import DialogoCliente, VistaClientes
from alquiler.ui.vistas.perfil import VistaPerfil
from alquiler.ui.vistas.usuarios import DialogoUsuario, VistaUsuarios


@pytest.fixture
def errores(monkeypatch):
    registrados = []
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, msg: registrados.append(msg))
    monkeypatch.setattr(widgets, "informar", lambda parent, msg: None)
    monkeypatch.setattr(widgets, "confirmar", lambda parent, texto: True)
    return registrados


def _dialogos(monkeypatch, rellenar, aceptar=True):
    monkeypatch.setattr(widgets, "ejecutar_dialogo", lambda dlg: (rellenar(dlg), aceptar)[1])


def test_vista_clientes_nuevo_busca_y_desactiva(qtbot, monkeypatch, ctx_factory, datos_base,
                                                errores):
    def rellenar(dlg: DialogoCliente):
        dlg.campo_documento.setText("777")
        dlg.campo_nombre.setText("Luis Gómez")
        dlg.campo_telefono.setText("3100000000")
    _dialogos(monkeypatch, rellenar)
    v = VistaClientes(ctx_factory("empleado"))
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    assert errores == [] and v.tabla.filas_mostradas() == 2
    v.campo_buscar.setText("luis")
    assert v.tabla.filas_mostradas() == 1
    v.tabla.selectRow(0)
    v.botones["desactivar"].click()
    assert v.tabla.filas_mostradas() == 0
    v.casilla_inactivos.setChecked(True)
    assert v.tabla.filas_mostradas() == 1 and v.tabla.texto(0, 4) == "Inactivo"


def test_vista_clientes_muestra_historial_del_seleccionado(qtbot, ctx_factory, datos_base):
    v = VistaClientes(ctx_factory("empleado"))
    qtbot.addWidget(v)
    v.tabla.selectRow(0)
    assert "Ana Pérez" in v.etiqueta_historial.text()
    assert v.tabla_historial.filas_mostradas() == 0


def test_vista_usuarios_crea_y_no_se_desactiva_a_si_mismo(qtbot, monkeypatch, ctx_factory,
                                                         errores):
    def rellenar(dlg: DialogoUsuario):
        dlg.campo_usuario.setText("luis")
        dlg.campo_nombre.setText("Luis Gómez")
        dlg.combo_rol.setCurrentIndex(dlg.combo_rol.findData("empleado"))
        dlg.campo_password.setText("clave-segura")
    _dialogos(monkeypatch, rellenar)
    v = VistaUsuarios(ctx_factory("admin"))
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    usernames = [v.tabla.texto(i, 0) for i in range(v.tabla.filas_mostradas())]
    assert errores == [] and usernames == ["admin", "luis"]
    v.tabla.selectRow(0)  # admin: él mismo
    v.botones["estado"].click()
    assert errores == ["No puede desactivar su propio usuario."]
    v.tabla.selectRow(1)
    v.botones["estado"].click()
    assert v.tabla.texto(1, 3) == "Inactivo"


def test_dialogo_usuario_cliente_requiere_cliente(qtbot, ctx_factory, datos_base):
    dlg = DialogoUsuario([{"id": 1, "etiqueta": "Ana Pérez — 1"}])
    qtbot.addWidget(dlg)
    assert not dlg.combo_cliente.isEnabled()
    dlg.combo_rol.setCurrentIndex(dlg.combo_rol.findData("cliente"))
    assert dlg.combo_cliente.isEnabled()


def test_perfil_cambio_password(qtbot, fabrica, config, errores):
    with fabrica() as s:
        crear_usuario(s, "luis", "clave-segura", Rol.EMPLEADO, "Luis")
    v = VistaPerfil(iniciar_sesion(fabrica, config, "luis", "clave-segura"))
    qtbot.addWidget(v)
    assert v.grupo_contacto is None  # un empleado no tiene ficha de cliente
    v.campo_actual.setText("equivocada")
    v.campo_nueva.setText("nueva-clave-1")
    v.campo_confirmar.setText("otra-cosa")
    v.boton_password.click()
    assert errores == ["Las contraseñas nuevas no coinciden."]
    v.campo_confirmar.setText("nueva-clave-1")
    v.boton_password.click()
    assert errores[-1] == "La contraseña actual no es correcta."
    v.campo_actual.setText("clave-segura")
    v.boton_password.click()
    assert len(errores) == 2 and v.campo_actual.text() == ""
    assert iniciar_sesion(fabrica, config, "luis", "nueva-clave-1")


def test_perfil_cliente_edita_contacto_y_ve_historial(qtbot, ctx_factory, datos_base, errores):
    v = VistaPerfil(ctx_factory("cliente"))
    qtbot.addWidget(v)
    assert v.grupo_contacto is not None and v.tabla_historial is not None
    v.campo_telefono.setText("3119998877")
    v.boton_contacto.click()
    assert errores == []
    v2 = VistaPerfil(ctx_factory("cliente"))
    qtbot.addWidget(v2)
    assert v2.campo_telefono.text() == "3119998877"
