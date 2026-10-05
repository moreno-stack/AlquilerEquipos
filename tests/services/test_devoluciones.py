"""Servicio de devoluciones: retraso, mora, daños y contadores de uso (spec §4.4)."""

from datetime import date

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import EstadoAlquiler, EstadoEquipo, TipoMantenimiento
from alquiler.services import devoluciones as svc
from tests.services.conftest import nuevo_alquiler

INICIO, FIN = date(2026, 3, 1), date(2026, 3, 4)  # 3 días × 25 000 = 75 000


@pytest.fixture
def alquiler(session, cliente, equipo):
    equipo.estado = EstadoEquipo.ALQUILADO
    return nuevo_alquiler(session, cliente, equipo, INICIO, FIN)


def _devolver(session, actor, alquiler, fecha=FIN, horas=8.0, factor=1.5, **kw):
    return svc.registrar_devolucion(session, actor, alquiler.id, fecha, horas, factor, **kw)


# ---------------------------------------------------------------- liquidación
def test_devolucion_a_tiempo_sin_mora(alquiler):
    assert svc.liquidar(alquiler, FIN, 1.5) == svc.Liquidacion(0, 0, 75_000)


def test_devolucion_anticipada_no_reembolsa(alquiler):
    assert svc.liquidar(alquiler, date(2026, 3, 2), 1.5) == svc.Liquidacion(0, 0, 75_000)


def test_mora_dos_dias_factor_1_5(alquiler):
    # 2 días × 25 000 × 1,5 = 75 000 de mora
    assert svc.liquidar(alquiler, date(2026, 3, 6), 1.5) == svc.Liquidacion(2, 75_000, 150_000)


def test_mora_redondeo_half_up(session, cliente, equipo):
    equipo.tarifa_diaria = 10_003
    alquiler = nuevo_alquiler(session, cliente, equipo, INICIO, FIN)
    # 10 003 × 1,5 = 15 004,5 → half-up 15 005 (round() de Python daría 15 004)
    assert svc.liquidar(alquiler, date(2026, 3, 5), 1.5).recargo_mora == 15_005


def test_penalizacion_se_suma_al_total(alquiler):
    assert svc.liquidar(alquiler, FIN, 1.5, penalizacion_danos=20_000).total == 95_000


# ---------------------------------------------------------------- registro
def test_devolucion_sin_danos_libera_equipo_y_suma_uso(session, empleado, alquiler, equipo):
    dev = _devolver(session, empleado, alquiler)
    assert (dev.dias_retraso, dev.recargo_mora, dev.total) == (0, 0, 75_000)
    assert alquiler.estado is EstadoAlquiler.FINALIZADO
    assert equipo.estado is EstadoEquipo.DISPONIBLE
    assert (equipo.usos_acumulados, equipo.horas_uso_acumuladas) == (1, 8.0)
    assert dev.registrado_por_id == empleado.id


def test_devolucion_tardia_registra_mora(session, empleado, alquiler):
    dev = _devolver(session, empleado, alquiler, fecha=date(2026, 3, 6))
    assert (dev.dias_retraso, dev.recargo_mora, dev.total) == (2, 75_000, 150_000)


def test_devolucion_con_danos_abre_correctivo(session, empleado, alquiler, equipo):
    dev = _devolver(session, empleado, alquiler, con_danos=True,
                    descripcion_danos="Mandril roto", penalizacion_danos=30_000)
    assert dev.total == 105_000
    assert equipo.estado is EstadoEquipo.EN_MANTENIMIENTO
    [correctivo] = equipo.mantenimientos
    assert correctivo.tipo is TipoMantenimiento.CORRECTIVO
    assert correctivo.descripcion == "Daños reportados en devolución: Mandril roto"
    assert (correctivo.fecha_inicio, correctivo.usos_al_momento) == (FIN, 1)


def test_danos_sin_descripcion_rechazado(session, empleado, alquiler):
    with pytest.raises(ReglaNegocioError, match="describ"):
        _devolver(session, empleado, alquiler, con_danos=True, descripcion_danos="  ")


def test_penalizacion_sin_danos_rechazada(session, empleado, alquiler):
    with pytest.raises(ReglaNegocioError, match="daños"):
        _devolver(session, empleado, alquiler, penalizacion_danos=10_000)


def test_penalizacion_negativa_rechazada(session, empleado, alquiler):
    with pytest.raises(ReglaNegocioError):
        _devolver(session, empleado, alquiler, con_danos=True, descripcion_danos="x",
                  penalizacion_danos=-1)


def test_fecha_devolucion_antes_del_inicio_rechazada(session, empleado, alquiler, equipo):
    with pytest.raises(ReglaNegocioError, match="anterior al inicio"):
        _devolver(session, empleado, alquiler, fecha=date(2026, 2, 28))
    assert alquiler.estado is EstadoAlquiler.ACTIVO and equipo.usos_acumulados == 0


def test_horas_negativas_rechazadas(session, empleado, alquiler):
    with pytest.raises(ReglaNegocioError, match="horas"):
        _devolver(session, empleado, alquiler, horas=-1)


def test_doble_devolucion_rechazada_sin_duplicar_usos(session, empleado, alquiler, equipo):
    _devolver(session, empleado, alquiler)
    with pytest.raises(ReglaNegocioError, match="no está activo"):
        _devolver(session, empleado, alquiler)
    assert equipo.usos_acumulados == 1


def test_devolver_reserva_rechazado(session, empleado, cliente, equipo):
    reserva = nuevo_alquiler(session, cliente, equipo, date(2026, 4, 1), date(2026, 4, 2),
                             EstadoAlquiler.RESERVADO)
    with pytest.raises(ReglaNegocioError, match="no está activo"):
        _devolver(session, empleado, reserva, fecha=date(2026, 4, 2))


def test_cliente_no_registra_devoluciones(session, usuario_cliente, alquiler):
    with pytest.raises(PermisoDenegado):
        _devolver(session, usuario_cliente, alquiler)
