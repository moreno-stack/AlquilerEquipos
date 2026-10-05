"""Servicio de mantenimiento preventivo/correctivo."""

from datetime import date

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import EstadoEquipo, TipoMantenimiento
from alquiler.services import mantenimiento as svc
from tests.services.conftest import HOY

PREV = TipoMantenimiento.PREVENTIVO


def _abrir(session, actor, equipo, descripcion="Cambio de escobillas", hoy=HOY, tipo=PREV):
    return svc.abrir_mantenimiento(session, actor, equipo.id, tipo, descripcion, hoy=hoy)


def test_abrir_preventivo_pasa_equipo_a_mantenimiento_y_guarda_usos(session, empleado, equipo):
    equipo.usos_acumulados = 12
    session.commit()
    m = _abrir(session, empleado, equipo)
    assert equipo.estado is EstadoEquipo.EN_MANTENIMIENTO
    assert (m.usos_al_momento, m.fecha_inicio, m.fecha_fin, m.tipo) == (12, HOY, None, PREV)


def test_abrir_en_equipo_alquilado_rechazado(session, empleado, equipo):
    equipo.estado = EstadoEquipo.ALQUILADO
    session.commit()
    with pytest.raises(ReglaNegocioError, match="solo se abre mantenimiento"):
        _abrir(session, empleado, equipo)
    assert equipo.mantenimientos == []
    assert equipo.estado is EstadoEquipo.ALQUILADO


def test_abrir_dos_veces_rechazado(session, empleado, equipo):
    _abrir(session, empleado, equipo)
    with pytest.raises(ReglaNegocioError, match="ya tiene un mantenimiento abierto"):
        _abrir(session, empleado, equipo)
    assert len(equipo.mantenimientos) == 1


def test_descripcion_vacia_rechazada(session, empleado, equipo):
    with pytest.raises(ReglaNegocioError):
        _abrir(session, empleado, equipo, descripcion="   ")
    assert equipo.estado is EstadoEquipo.DISPONIBLE


def test_cliente_no_abre_mantenimientos(session, usuario_cliente, equipo):
    with pytest.raises(PermisoDenegado):
        _abrir(session, usuario_cliente, equipo)


def test_cerrar_devuelve_disponible_con_costo_y_fecha(session, empleado, equipo):
    m = _abrir(session, empleado, equipo)
    svc.cerrar_mantenimiento(session, empleado, m.id, costo=40_000, notas="Escobillas nuevas",
                             hoy=date(2026, 3, 12))
    assert equipo.estado is EstadoEquipo.DISPONIBLE
    assert (m.fecha_fin, m.costo) == (date(2026, 3, 12), 40_000)
    assert "Escobillas nuevas" in m.descripcion and "Cambio de escobillas" in m.descripcion


def test_cerrar_ya_cerrado_rechazado(session, empleado, equipo):
    m = _abrir(session, empleado, equipo)
    svc.cerrar_mantenimiento(session, empleado, m.id, hoy=HOY)
    with pytest.raises(ReglaNegocioError, match="ya está cerrado"):
        svc.cerrar_mantenimiento(session, empleado, m.id, hoy=HOY)


def test_costo_negativo_rechazado(session, empleado, equipo):
    m = _abrir(session, empleado, equipo)
    with pytest.raises(ReglaNegocioError):
        svc.cerrar_mantenimiento(session, empleado, m.id, costo=-1, hoy=HOY)
    assert m.fecha_fin is None and equipo.estado is EstadoEquipo.EN_MANTENIMIENTO


def test_cerrar_antes_de_abrir_rechazado(session, empleado, equipo):
    m = _abrir(session, empleado, equipo)
    with pytest.raises(ReglaNegocioError):
        svc.cerrar_mantenimiento(session, empleado, m.id, hoy=date(2026, 3, 9))


def test_rehabilitar_fuera_de_servicio(session, empleado, equipo):
    equipo.estado = EstadoEquipo.FUERA_DE_SERVICIO
    session.commit()
    m = _abrir(session, empleado, equipo, tipo=TipoMantenimiento.CORRECTIVO)
    assert equipo.estado is EstadoEquipo.EN_MANTENIMIENTO
    svc.cerrar_mantenimiento(session, empleado, m.id, hoy=HOY)
    assert equipo.estado is EstadoEquipo.DISPONIBLE


def test_historial_descendente_y_abiertos(session, empleado, equipo):
    viejo = _abrir(session, empleado, equipo, hoy=date(2026, 1, 5))
    svc.cerrar_mantenimiento(session, empleado, viejo.id, hoy=date(2026, 1, 6))
    nuevo = _abrir(session, empleado, equipo, hoy=HOY)
    assert svc.historial_mantenimiento(session, empleado, equipo.id) == [nuevo, viejo]
    assert svc.mantenimientos_abiertos(session, empleado) == [nuevo]
