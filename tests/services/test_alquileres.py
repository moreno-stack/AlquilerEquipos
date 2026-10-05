"""Servicio de alquileres y pagos (spec §4.4)."""

from datetime import date, timedelta

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import (
    ConceptoPago,
    Devolucion,
    EstadoAlquiler,
    EstadoEquipo,
    MetodoPago,
)
from alquiler.services import alquileres as svc
from tests.services.conftest import HOY, nuevo_alquiler


def _crear(session, actor, cliente, equipo, inicio=HOY, fin=HOY + timedelta(days=3)):
    return svc.crear_alquiler(session, actor, cliente.id, equipo.id, inicio, fin, hoy=HOY)


def _pagar(session, actor, alquiler, monto, concepto=ConceptoPago.ALQUILER):
    return svc.registrar_pago(session, actor, alquiler.id, monto, MetodoPago.EFECTIVO,
                              concepto, hoy=HOY)


# ---------------------------------------------------------------- cálculos puros
def test_costo_mismo_dia_cobra_un_dia():
    assert svc.dias_contratados(HOY, HOY) == 1
    assert svc.calcular_costo(HOY, HOY, 25_000) == 25_000


def test_costo_tres_dias():
    assert svc.calcular_costo(date(2026, 3, 1), date(2026, 3, 4), 25_000) == 75_000


# ---------------------------------------------------------------- creación
def test_alquiler_hoy_queda_activo_y_equipo_alquilado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    assert alquiler.estado is EstadoAlquiler.ACTIVO
    assert equipo.estado is EstadoEquipo.ALQUILADO
    assert alquiler.costo_estimado == 75_000
    assert alquiler.registrado_por is empleado


def test_alquiler_futuro_queda_reservado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo, HOY + timedelta(days=5),
                      HOY + timedelta(days=6))
    assert alquiler.estado is EstadoAlquiler.RESERVADO
    assert equipo.estado is EstadoEquipo.RESERVADO


def test_tarifa_se_congela_al_contratar(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    equipo.tarifa_diaria = 99_000
    session.commit()
    assert (alquiler.tarifa_diaria, alquiler.costo_estimado) == (25_000, 75_000)


def test_fecha_inicio_pasada_rechazada(session, empleado, cliente, equipo):
    with pytest.raises(ReglaNegocioError, match="pasada"):
        _crear(session, empleado, cliente, equipo, HOY - timedelta(days=1), HOY)


def test_fin_antes_de_inicio_rechazado(session, empleado, cliente, equipo):
    with pytest.raises(ReglaNegocioError):
        _crear(session, empleado, cliente, equipo, HOY + timedelta(days=2), HOY + timedelta(days=1))


def test_equipo_no_disponible_rechazado(session, empleado, cliente, equipo):
    equipo.estado = EstadoEquipo.EN_MANTENIMIENTO
    session.commit()
    with pytest.raises(ReglaNegocioError, match="no está disponible"):
        _crear(session, empleado, cliente, equipo)


def test_equipo_ya_alquilado_no_se_alquila_dos_veces(session, empleado, cliente, equipo):
    _crear(session, empleado, cliente, equipo)
    with pytest.raises(ReglaNegocioError, match="no está disponible"):
        _crear(session, empleado, cliente, equipo)


def test_cliente_inactivo_rechazado(session, empleado, cliente, equipo):
    cliente.activo = False
    session.commit()
    with pytest.raises(ReglaNegocioError, match="inactivo"):
        _crear(session, empleado, cliente, equipo)
    assert equipo.estado is EstadoEquipo.DISPONIBLE


def test_cliente_no_puede_crear_alquiler(session, usuario_cliente, cliente, equipo):
    with pytest.raises(PermisoDenegado):
        _crear(session, usuario_cliente, cliente, equipo)


# ---------------------------------------------------------------- reservas
def test_entregar_reserva(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo, HOY + timedelta(days=2),
                      HOY + timedelta(days=4))
    svc.entregar_reserva(session, empleado, alquiler.id, hoy=HOY + timedelta(days=2))
    assert alquiler.estado is EstadoAlquiler.ACTIVO
    assert equipo.estado is EstadoEquipo.ALQUILADO


def test_entregar_antes_de_inicio_rechazado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo, HOY + timedelta(days=2),
                      HOY + timedelta(days=4))
    with pytest.raises(ReglaNegocioError):
        svc.entregar_reserva(session, empleado, alquiler.id, hoy=HOY)
    assert alquiler.estado is EstadoAlquiler.RESERVADO


def test_entregar_alquiler_activo_rechazado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    with pytest.raises(ReglaNegocioError, match="reservado"):
        svc.entregar_reserva(session, empleado, alquiler.id, hoy=HOY)


def test_cancelar_reserva_libera_equipo(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo, HOY + timedelta(days=2),
                      HOY + timedelta(days=4))
    svc.cancelar_alquiler(session, empleado, alquiler.id)
    assert alquiler.estado is EstadoAlquiler.CANCELADO
    assert equipo.estado is EstadoEquipo.DISPONIBLE


def test_cancelar_activo_rechazado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    with pytest.raises(ReglaNegocioError, match="reservado"):
        svc.cancelar_alquiler(session, empleado, alquiler.id)
    assert equipo.estado is EstadoEquipo.ALQUILADO


# ---------------------------------------------------------------- pagos
def test_pago_parcial_reduce_saldo(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    pago = _pagar(session, empleado, alquiler, 50_000)
    assert pago.fecha == HOY
    assert svc.saldo_pendiente(alquiler) == 25_000
    _pagar(session, empleado, alquiler, 25_000)
    assert svc.saldo_pendiente(alquiler) == 0


def test_pago_mayor_al_saldo_rechazado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    _pagar(session, empleado, alquiler, 70_000)
    with pytest.raises(ReglaNegocioError, match=r"saldo pendiente \(\$5\.000\)"):
        _pagar(session, empleado, alquiler, 5_001)
    assert len(alquiler.pagos) == 1


def test_pago_no_positivo_rechazado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo)
    with pytest.raises(ReglaNegocioError):
        _pagar(session, empleado, alquiler, 0)


def test_pago_a_cancelado_rechazado(session, empleado, cliente, equipo):
    alquiler = _crear(session, empleado, cliente, equipo, HOY + timedelta(days=2),
                      HOY + timedelta(days=4))
    svc.cancelar_alquiler(session, empleado, alquiler.id)
    with pytest.raises(ReglaNegocioError, match="cancelado"):
        _pagar(session, empleado, alquiler, 1_000)


def test_saldo_usa_el_total_de_la_devolucion(session, cliente, equipo):
    alquiler = nuevo_alquiler(session, cliente, equipo, estado=EstadoAlquiler.FINALIZADO)
    session.add(Devolucion(alquiler=alquiler, fecha_devolucion=date(2026, 3, 6), dias_retraso=2,
                           recargo_mora=75_000, horas_uso=10, total=150_000))
    session.commit()
    assert svc.total_adeudado(alquiler) == 150_000
    assert svc.saldo_pendiente(alquiler) == 150_000


# ---------------------------------------------------------------- consultas
def test_vencidos_solo_activos_con_fin_pasado(session, empleado, cliente, equipo, categoria):
    vencido = nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 9))
    nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), HOY)  # vence hoy: aún no
    nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 5),
                   EstadoAlquiler.FINALIZADO)
    assert svc.alquileres_vencidos(session, empleado, hoy=HOY) == [vencido]


def test_listar_filtra_por_estado_y_cliente(session, empleado, cliente, equipo):
    activo = nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 4))
    final = nuevo_alquiler(session, cliente, equipo, date(2026, 2, 1), date(2026, 2, 4),
                           EstadoAlquiler.FINALIZADO)
    assert svc.listar_alquileres(session, empleado) == [activo, final]
    assert svc.listar_alquileres(session, empleado, estado=EstadoAlquiler.FINALIZADO) == [final]
    assert svc.listar_alquileres(session, empleado, cliente_id=cliente.id + 1) == []


def test_entregar_reserva_vencida_rechazado(session, empleado, cliente, equipo):
    # Entregarla crearía un alquiler que nace vencido y cobra mora desde el día 1.
    alquiler = _crear(session, empleado, cliente, equipo, HOY + timedelta(days=2),
                      HOY + timedelta(days=4))
    with pytest.raises(ReglaNegocioError, match="venció"):
        svc.entregar_reserva(session, empleado, alquiler.id, hoy=HOY + timedelta(days=5))
    assert alquiler.estado is EstadoAlquiler.RESERVADO
