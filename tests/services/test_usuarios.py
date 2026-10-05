"""Servicio de usuarios: alta con RBAC, activación y contraseñas."""

import pytest

from alquiler.auth import autenticar
from alquiler.auth import crear_usuario as crear_directo
from alquiler.errors import CredencialesInvalidas, PermisoDenegado, ReglaNegocioError
from alquiler.models import Rol
from alquiler.services import usuarios as svc
from tests.services.conftest import nuevo_usuario

PWD = "clave-segura-1"


def test_admin_crea_empleado(session, admin):
    u = svc.crear_usuario(session, admin, "luis", PWD, Rol.EMPLEADO, "Luis Gómez")
    assert autenticar(session, "luis", PWD).id == u.id


def test_empleado_no_crea_usuarios(session, empleado):
    with pytest.raises(PermisoDenegado):
        svc.crear_usuario(session, empleado, "luis", PWD, Rol.EMPLEADO, "Luis")


def test_nombre_completo_vacio_rechazado(session, admin):
    with pytest.raises(ReglaNegocioError, match="nombre completo"):
        svc.crear_usuario(session, admin, "luis", PWD, Rol.EMPLEADO, "   ")


def test_listar_usuarios_ordenados(session, admin, empleado):
    assert [u.username for u in svc.listar_usuarios(session, admin)] == ["admin", "empleado"]
    with pytest.raises(PermisoDenegado):
        svc.listar_usuarios(session, empleado)


def test_admin_no_se_desactiva_a_si_mismo(session, admin):
    nuevo_usuario(session, "jefa", Rol.ADMIN)
    with pytest.raises(ReglaNegocioError, match="propio"):
        svc.cambiar_estado_usuario(session, admin, admin.id, activo=False)
    assert admin.activo


def test_admin_desactiva_a_otro_admin(session, admin):
    jefa = nuevo_usuario(session, "jefa", Rol.ADMIN)
    svc.cambiar_estado_usuario(session, jefa, admin.id, activo=False)
    assert not admin.activo


def test_admin_inactivo_no_puede_actuar(session, admin):
    jefa = nuevo_usuario(session, "jefa", Rol.ADMIN)
    svc.cambiar_estado_usuario(session, jefa, admin.id, activo=False)
    # Como nadie puede desactivarse a sí mismo, siempre queda al menos un admin activo.
    with pytest.raises(PermisoDenegado):
        svc.cambiar_estado_usuario(session, admin, jefa.id, activo=False)
    assert jefa.activo


def test_desactivar_y_reactivar_empleado(session, admin, empleado):
    svc.cambiar_estado_usuario(session, admin, empleado.id, activo=False)
    assert not empleado.activo
    svc.cambiar_estado_usuario(session, admin, empleado.id, activo=True)
    assert empleado.activo


def test_cambiar_password_propia(session):
    u = crear_directo(session, "luis", PWD, Rol.EMPLEADO, "Luis")
    svc.cambiar_password(session, u, actual=PWD, nueva="otra-clave-2")
    assert autenticar(session, "luis", "otra-clave-2").id == u.id
    with pytest.raises(CredencialesInvalidas):
        autenticar(session, "luis", PWD)


def test_cambiar_password_con_actual_incorrecta(session):
    u = crear_directo(session, "luis", PWD, Rol.EMPLEADO, "Luis")
    with pytest.raises(CredencialesInvalidas):
        svc.cambiar_password(session, u, actual="equivocada", nueva="otra-clave-2")
    assert autenticar(session, "luis", PWD).id == u.id


def test_nueva_password_corta_rechazada(session):
    u = crear_directo(session, "luis", PWD, Rol.EMPLEADO, "Luis")
    with pytest.raises(ReglaNegocioError, match="8 caracteres"):
        svc.cambiar_password(session, u, actual=PWD, nueva="corta")


def test_cliente_cambia_su_password(session, cliente):
    u = crear_directo(session, "ana", PWD, Rol.CLIENTE, "Ana", cliente_id=cliente.id)
    svc.cambiar_password(session, u, actual=PWD, nueva="nueva-clave-3")
    assert autenticar(session, "ana", "nueva-clave-3").id == u.id


def test_restablecer_password_por_admin(session, admin, empleado):
    svc.restablecer_password(session, admin, empleado.id, "temporal-123")
    assert autenticar(session, "empleado", "temporal-123").id == empleado.id
    with pytest.raises(PermisoDenegado):
        svc.restablecer_password(session, empleado, admin.id, "temporal-123")
