"""Fixtures de la capa de servicios.

Los usuarios se crean directamente en el modelo con un hash ficticio para no
pagar el costo de bcrypt en cada prueba.
"""

from datetime import date

import pytest

from alquiler.models import Alquiler, Categoria, Cliente, Equipo, EstadoAlquiler, Rol, Usuario

HOY = date(2026, 3, 10)


def nuevo_usuario(session, username, rol, cliente=None):
    usuario = Usuario(username=username, password_hash="x", nombre_completo=username.title(),
                      rol=rol, cliente=cliente)
    session.add(usuario)
    session.commit()
    return usuario


def nuevo_alquiler(session, cliente, equipo, inicio=date(2026, 3, 1), fin=date(2026, 3, 4),
                   estado=EstadoAlquiler.ACTIVO):
    """Inserta un alquiler directamente (sin pasar por el servicio)."""
    alquiler = Alquiler(cliente=cliente, equipo=equipo, fecha_inicio=inicio,
                        fecha_fin_prevista=fin, tarifa_diaria=equipo.tarifa_diaria,
                        costo_estimado=max(1, (fin - inicio).days) * equipo.tarifa_diaria,
                        estado=estado)
    session.add(alquiler)
    session.commit()
    return alquiler


@pytest.fixture
def admin(session):
    return nuevo_usuario(session, "admin", Rol.ADMIN)


@pytest.fixture
def empleado(session):
    return nuevo_usuario(session, "empleado", Rol.EMPLEADO)


@pytest.fixture
def cliente(session):
    c = Cliente(documento="1085000001", nombre="Ana Pérez", telefono="3001234567")
    session.add(c)
    session.commit()
    return c


@pytest.fixture
def usuario_cliente(session, cliente):
    return nuevo_usuario(session, "ana", Rol.CLIENTE, cliente=cliente)


@pytest.fixture
def categoria(session):
    c = Categoria(nombre="Taladros", intervalo_mant_usos=20, intervalo_mant_dias=90)
    session.add(c)
    session.commit()
    return c


@pytest.fixture
def equipo(session, categoria):
    e = Equipo(codigo="TAL-001", nombre="Taladro percutor", categoria=categoria,
               tarifa_diaria=25_000, fecha_adquisicion=date(2025, 1, 10))
    session.add(e)
    session.commit()
    return e
