"""Servicio de clientes: registro, perfil propio, bajas e historial."""

from datetime import date

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import Cliente, EstadoAlquiler
from alquiler.services import clientes as svc
from tests.services.conftest import nuevo_alquiler


def test_registrar_cliente(session, empleado):
    c = svc.registrar_cliente(session, empleado, " 1085999 ", " Luis Gómez ", "3109998877",
                              email="luis@correo.co")
    assert (c.documento, c.nombre, c.activo) == ("1085999", "Luis Gómez", True)


def test_documento_duplicado_con_espacios(session, empleado, cliente):
    with pytest.raises(ReglaNegocioError, match="1085000001"):
        svc.registrar_cliente(session, empleado, " 1085000001 ", "Otra", "300")


@pytest.mark.parametrize("email", ["sin-arroba.co", "a@b", "a b@c.co"])
def test_email_invalido_rechazado(session, empleado, email):
    with pytest.raises(ReglaNegocioError, match="correo"):
        svc.registrar_cliente(session, empleado, "1", "Luis", "300", email=email)


@pytest.mark.parametrize("campo", ["documento", "nombre"])
def test_documento_y_nombre_obligatorios(session, empleado, campo):
    datos = {"documento": "1", "nombre": "Luis", "telefono": "300", campo: "   "}
    with pytest.raises(ReglaNegocioError):
        svc.registrar_cliente(session, empleado, **datos)


def test_cliente_no_puede_registrar_clientes(session, usuario_cliente):
    with pytest.raises(PermisoDenegado):
        svc.registrar_cliente(session, usuario_cliente, "2", "Luis", "300")


def test_empleado_actualiza_nombre(session, empleado, cliente):
    svc.actualizar_cliente(session, empleado, cliente.id, nombre="Ana P. Ruiz")
    assert cliente.nombre == "Ana P. Ruiz"


def test_cliente_edita_su_telefono(session, usuario_cliente, cliente):
    svc.actualizar_cliente(session, usuario_cliente, cliente.id, telefono="3110000000")
    assert cliente.telefono == "3110000000"


def test_cliente_no_edita_su_nombre(session, usuario_cliente, cliente):
    with pytest.raises(PermisoDenegado):
        svc.actualizar_cliente(session, usuario_cliente, cliente.id, nombre="Otro")
    assert cliente.nombre == "Ana Pérez"


def test_cliente_no_edita_a_otro(session, usuario_cliente):
    otro = Cliente(documento="2", nombre="Otro", telefono="3")
    session.add(otro)
    session.commit()
    with pytest.raises(PermisoDenegado):
        svc.actualizar_cliente(session, usuario_cliente, otro.id, telefono="1")


def test_actualizar_documento_no_permitido(session, empleado, cliente):
    with pytest.raises(ReglaNegocioError, match="documento"):
        svc.actualizar_cliente(session, empleado, cliente.id, documento="999")


def test_actualizar_con_email_invalido_no_deja_cambios(session, empleado, cliente):
    with pytest.raises(ReglaNegocioError):
        svc.actualizar_cliente(session, empleado, cliente.id, telefono="1", email="malo")
    assert cliente.telefono == "3001234567"


def test_cliente_ve_su_historial_y_no_el_ajeno(session, usuario_cliente, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo)
    otro = Cliente(documento="2", nombre="Otro", telefono="3")
    session.add(otro)
    session.commit()
    assert len(svc.historial_cliente(session, usuario_cliente, cliente.id)) == 1
    with pytest.raises(PermisoDenegado):
        svc.historial_cliente(session, usuario_cliente, otro.id)
    with pytest.raises(PermisoDenegado):
        svc.obtener_cliente(session, usuario_cliente, otro.id)


def test_desactivar_con_alquiler_activo_rechazado(session, empleado, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo)
    with pytest.raises(ReglaNegocioError, match="alquileres"):
        svc.desactivar_cliente(session, empleado, cliente.id)
    assert cliente.activo


def test_desactivado_no_aparece_en_busqueda_por_defecto(session, empleado, cliente):
    svc.desactivar_cliente(session, empleado, cliente.id)
    assert svc.buscar_clientes(session, empleado) == []
    assert svc.buscar_clientes(session, empleado, incluir_inactivos=True) == [cliente]


def test_buscar_por_nombre_o_documento(session, empleado, cliente):
    svc.registrar_cliente(session, empleado, "7777", "Luis Gómez", "300")
    assert [c.documento for c in svc.buscar_clientes(session, empleado, texto="ana")] == ["1085000001"]
    assert [c.nombre for c in svc.buscar_clientes(session, empleado, texto="777")] == ["Luis Gómez"]
    assert [c.nombre for c in svc.buscar_clientes(session, empleado)] == ["Ana Pérez", "Luis Gómez"]


def test_historial_ordenado_del_mas_reciente(session, empleado, cliente, equipo):
    viejo = nuevo_alquiler(session, cliente, equipo, date(2026, 1, 5), date(2026, 1, 7),
                           EstadoAlquiler.FINALIZADO)
    nuevo = nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 4))
    assert svc.historial_cliente(session, empleado, cliente.id) == [nuevo, viejo]


def test_alquileres_activos_excluye_finalizados_y_cancelados(session, empleado, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo, estado=EstadoAlquiler.FINALIZADO)
    nuevo_alquiler(session, cliente, equipo, estado=EstadoAlquiler.CANCELADO)
    activo = nuevo_alquiler(session, cliente, equipo)
    reservado = nuevo_alquiler(session, cliente, equipo, date(2026, 4, 1), date(2026, 4, 2),
                               EstadoAlquiler.RESERVADO)
    assert svc.alquileres_activos_cliente(session, empleado, cliente.id) == [reservado, activo]


def test_desactivar_cliente_bloquea_su_usuario(session, empleado, cliente, usuario_cliente):
    # Un cliente dado de baja no debe poder seguir entrando al sistema.
    svc.desactivar_cliente(session, empleado, cliente.id)
    assert usuario_cliente.activo is False
