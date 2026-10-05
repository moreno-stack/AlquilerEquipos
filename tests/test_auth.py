"""Autenticación y RBAC (spec §5)."""

import pytest

from alquiler.auth import (
    PERMISOS_POR_ROL,
    Permiso,
    asegurar_admin_inicial,
    autenticar,
    crear_usuario,
    hash_password,
    requerir_permiso,
    tiene_permiso,
    verificar_password,
)
from alquiler.errors import CredencialesInvalidas, PermisoDenegado, ReglaNegocioError
from alquiler.models import Cliente, Rol, Usuario

PWD = "secreta123"


def _empleado(session, username="ana", **kw):
    datos = dict(username=username, password=PWD, rol=Rol.EMPLEADO, nombre_completo="Ana Ruiz")
    datos.update(kw)
    return crear_usuario(session, **datos)


# ---------------------------------------------------------------- contraseñas
def test_hash_no_es_texto_plano_y_verifica():
    h = hash_password(PWD)
    assert PWD not in h
    assert verificar_password(PWD, h)
    assert not verificar_password("otra-clave", h)


def test_hash_con_sal_distinta():
    assert hash_password(PWD) != hash_password(PWD)


def test_password_corta_rechazada(session):
    with pytest.raises(ReglaNegocioError, match="8 caracteres"):
        _empleado(session, password="1234567")


def test_password_mayor_72_bytes_rechazada(session):
    # 37 "ñ" son 37 caracteres pero 74 bytes UTF-8: bcrypt solo usa 72.
    with pytest.raises(ReglaNegocioError, match="72 bytes"):
        _empleado(session, password="ñ" * 37)


def test_password_de_72_bytes_aceptada(session):
    usuario = _empleado(session, password="ñ" * 36)
    assert verificar_password("ñ" * 36, usuario.password_hash)


def test_hash_no_se_guarda_en_texto_plano(session):
    assert _empleado(session).password_hash != PWD


# ---------------------------------------------------------------- creación
def test_username_se_normaliza(session):
    usuario = _empleado(session, username=" Admin ")
    assert usuario.username == "admin"
    assert autenticar(session, "ADMIN", PWD).id == usuario.id
    assert autenticar(session, "  admin ", PWD).id == usuario.id


def test_username_vacio_rechazado(session):
    with pytest.raises(ReglaNegocioError):
        _empleado(session, username="   ")


def test_username_duplicado_rechazado(session):
    _empleado(session, username="ana")
    with pytest.raises(ReglaNegocioError, match="ya existe"):
        _empleado(session, username="ANA")


def test_rol_cliente_requiere_cliente_id(session):
    with pytest.raises(ReglaNegocioError):
        _empleado(session, rol=Rol.CLIENTE)


def test_rol_no_cliente_no_admite_cliente_id(session):
    cliente = Cliente(documento="1", nombre="C", telefono="3")
    session.add(cliente)
    session.flush()
    with pytest.raises(ReglaNegocioError):
        _empleado(session, cliente_id=cliente.id)


def test_usuario_cliente_queda_enlazado(session):
    cliente = Cliente(documento="1", nombre="C", telefono="3")
    session.add(cliente)
    session.flush()
    usuario = _empleado(session, username="cli", rol=Rol.CLIENTE, cliente_id=cliente.id)
    assert usuario.cliente.documento == "1"


# ---------------------------------------------------------------- autenticación
def test_autenticar_credenciales_validas(session):
    usuario = _empleado(session)
    assert autenticar(session, "ana", PWD).id == usuario.id


def test_autenticar_no_revela_si_existe_el_usuario(session):
    _empleado(session)
    with pytest.raises(CredencialesInvalidas) as mal_password:
        autenticar(session, "ana", "incorrecta")
    with pytest.raises(CredencialesInvalidas) as inexistente:
        autenticar(session, "nadie", PWD)
    assert str(mal_password.value) == str(inexistente.value)


def test_login_con_password_larguisima_no_revienta(session):
    _empleado(session)
    with pytest.raises(CredencialesInvalidas):
        autenticar(session, "ana", "x" * 200)


def test_usuario_inactivo_no_entra(session):
    usuario = _empleado(session)
    usuario.activo = False
    session.commit()
    with pytest.raises(CredencialesInvalidas):
        autenticar(session, "ana", PWD)


# ---------------------------------------------------------------- RBAC
def test_admin_tiene_todos_los_permisos():
    assert PERMISOS_POR_ROL[Rol.ADMIN] == frozenset(Permiso)


def test_hay_15_permisos():
    assert len(Permiso) == 15


SOLO_ADMIN = {Permiso.EQUIPOS_ELIMINAR, Permiso.IA_CONSULTAS, Permiso.REPORTES_VER,
              Permiso.USUARIOS_GESTIONAR}
CLIENTE = {Permiso.CATALOGO_VER, Permiso.PERFIL_PROPIO}


@pytest.mark.parametrize("permiso", list(Permiso))
def test_matriz_empleado(permiso):
    assert (permiso in PERMISOS_POR_ROL[Rol.EMPLEADO]) is (permiso not in SOLO_ADMIN)


@pytest.mark.parametrize("permiso", list(Permiso))
def test_matriz_cliente(permiso):
    assert (permiso in PERMISOS_POR_ROL[Rol.CLIENTE]) is (permiso in CLIENTE)


def test_tiene_permiso_usa_el_rol_del_usuario():
    empleado = Usuario(username="e", password_hash="h", nombre_completo="E", rol=Rol.EMPLEADO)
    assert tiene_permiso(empleado, Permiso.ALQUILERES_GESTIONAR)
    assert not tiene_permiso(empleado, Permiso.REPORTES_VER)


def test_usuario_inactivo_no_tiene_permisos():
    admin = Usuario(username="a", password_hash="h", nombre_completo="A", rol=Rol.ADMIN,
                    activo=False)
    assert not tiene_permiso(admin, Permiso.CATALOGO_VER)


def test_requerir_permiso_lanza_permiso_denegado():
    cliente = Usuario(username="c", password_hash="h", nombre_completo="C", rol=Rol.CLIENTE)
    requerir_permiso(cliente, Permiso.CATALOGO_VER)
    with pytest.raises(PermisoDenegado):
        requerir_permiso(cliente, Permiso.ALQUILERES_GESTIONAR)


# ---------------------------------------------------------------- admin inicial
def test_admin_inicial_se_crea_una_sola_vez(session):
    admin = asegurar_admin_inicial(session, "admin1234")
    assert admin.username == "admin" and admin.rol is Rol.ADMIN
    assert autenticar(session, "admin", "admin1234").id == admin.id
    assert asegurar_admin_inicial(session, "otra-clave") is None
    assert session.query(Usuario).filter_by(rol=Rol.ADMIN).count() == 1


def test_admin_inicial_no_se_crea_si_ya_hay_otro_admin(session):
    _empleado(session, username="jefa", rol=Rol.ADMIN)
    assert asegurar_admin_inicial(session, "admin1234") is None
