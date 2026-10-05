"""Servicio de reportes: ingresos, uso de flota y morosidad (spec §7)."""

from datetime import date

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import (
    ConceptoPago,
    Devolucion,
    Equipo,
    EstadoAlquiler,
    MetodoPago,
    Pago,
)
from alquiler.services import reportes as svc
from tests.services.conftest import HOY, nuevo_alquiler

MARZO = (date(2026, 3, 1), date(2026, 3, 10))  # 10 días


def _pago(session, alquiler, monto, fecha, concepto=ConceptoPago.ALQUILER):
    session.add(Pago(alquiler=alquiler, monto=monto, fecha=fecha, metodo=MetodoPago.EFECTIVO,
                     concepto=concepto))
    session.commit()


def _devuelto(session, cliente, equipo, inicio, fin_prevista, devolucion, retraso=0, mora=0):
    alquiler = nuevo_alquiler(session, cliente, equipo, inicio, fin_prevista,
                              EstadoAlquiler.FINALIZADO)
    session.add(Devolucion(alquiler=alquiler, fecha_devolucion=devolucion, dias_retraso=retraso,
                           recargo_mora=mora, horas_uso=1, total=alquiler.costo_estimado + mora))
    session.commit()
    return alquiler


# ---------------------------------------------------------------- ingresos
def test_ingresos_suma_por_concepto_y_mes(session, admin, cliente, equipo):
    a = nuevo_alquiler(session, cliente, equipo)
    _pago(session, a, 50_000, date(2026, 2, 20))
    _pago(session, a, 25_000, date(2026, 3, 2))
    _pago(session, a, 10_000, date(2026, 3, 5), ConceptoPago.MORA)
    _pago(session, a, 99_000, date(2026, 4, 1))  # fuera del período
    r = svc.ingresos(session, admin, date(2026, 2, 1), date(2026, 3, 31))
    assert r.total == 85_000
    assert r.por_concepto == {ConceptoPago.ALQUILER: 75_000, ConceptoPago.MORA: 10_000,
                              ConceptoPago.DANOS: 0}
    assert r.por_mes == {"2026-02": 50_000, "2026-03": 35_000}


def test_periodo_invertido_rechazado(session, admin):
    with pytest.raises(ReglaNegocioError, match="período"):
        svc.ingresos(session, admin, date(2026, 3, 10), date(2026, 3, 1))
    with pytest.raises(ReglaNegocioError, match="período"):
        svc.uso_flota(session, admin, date(2026, 3, 10), date(2026, 3, 1), hoy=HOY)


def test_periodo_sin_datos_da_ceros(session, admin):
    r = svc.ingresos(session, admin, *MARZO)
    assert r.total == 0 and r.por_mes == {}
    assert set(r.por_concepto.values()) == {0} and len(r.por_concepto) == 3
    assert svc.uso_flota(session, admin, *MARZO, hoy=HOY) == []
    assert svc.uso_por_categoria(session, admin, *MARZO, hoy=HOY) == {}


# ---------------------------------------------------------------- uso de flota
def test_uso_flota_porcentaje(session, admin, cliente, equipo):
    _devuelto(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 4), date(2026, 3, 4))
    [uso] = svc.uso_flota(session, admin, *MARZO, hoy=HOY)
    assert (uso.codigo, uso.categoria, uso.dias_alquilado, uso.dias_periodo, uso.porcentaje) == (
        "TAL-001", "Taladros", 3, 10, 30.0)


def test_uso_flota_alquiler_de_un_dia_cuenta_uno(session, admin, cliente, equipo):
    _devuelto(session, cliente, equipo, date(2026, 3, 5), date(2026, 3, 5), date(2026, 3, 5))
    assert svc.uso_flota(session, admin, *MARZO, hoy=HOY)[0].dias_alquilado == 1


def test_uso_flota_recorta_al_periodo(session, admin, cliente, equipo):
    _devuelto(session, cliente, equipo, date(2026, 2, 25), date(2026, 3, 3), date(2026, 3, 3))
    assert svc.uso_flota(session, admin, *MARZO, hoy=HOY)[0].dias_alquilado == 2


def test_uso_flota_activo_cuenta_hasta_hoy(session, admin, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo, date(2026, 3, 8), date(2026, 3, 20))
    [uso] = svc.uso_flota(session, admin, date(2026, 3, 1), date(2026, 3, 31), hoy=HOY)
    assert (uso.dias_alquilado, uso.dias_periodo, uso.porcentaje) == (3, 31, 9.7)


def test_uso_flota_ignora_cancelados_y_reservados(session, admin, cliente, equipo):
    nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 5),
                   EstadoAlquiler.CANCELADO)
    nuevo_alquiler(session, cliente, equipo, date(2026, 3, 2), date(2026, 3, 5),
                   EstadoAlquiler.RESERVADO)
    assert svc.uso_flota(session, admin, *MARZO, hoy=HOY)[0].dias_alquilado == 0


def test_equipo_sin_uso_aparece_con_cero_y_orden(session, admin, cliente, equipo, categoria):
    otro = Equipo(codigo="AAA-001", nombre="Pulidora", categoria=categoria, tarifa_diaria=1,
                  fecha_adquisicion=date(2025, 1, 1))
    session.add(otro)
    session.commit()
    _devuelto(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 4), date(2026, 3, 4))
    usos = svc.uso_flota(session, admin, *MARZO, hoy=HOY)
    assert [(u.codigo, u.porcentaje) for u in usos] == [("TAL-001", 30.0), ("AAA-001", 0.0)]
    assert svc.uso_por_categoria(session, admin, *MARZO, hoy=HOY) == {"Taladros": 15.0}


# ---------------------------------------------------------------- morosidad
def test_morosidad_vencidos_y_mora_estimada(session, admin, cliente, equipo):
    vencido = nuevo_alquiler(session, cliente, equipo, date(2026, 3, 1), date(2026, 3, 8))
    a = _devuelto(session, cliente, equipo, date(2026, 2, 1), date(2026, 2, 3), date(2026, 2, 5),
                  retraso=2, mora=75_000)
    _devuelto(session, cliente, equipo, date(2026, 2, 10), date(2026, 2, 12), date(2026, 2, 12))
    _pago(session, a, 30_000, date(2026, 2, 5), ConceptoPago.MORA)
    m = svc.morosidad(session, admin, factor_mora=1.5, hoy=HOY)
    [v] = m.vencidos
    assert (v.alquiler_id, v.cliente, v.equipo, v.dias_vencido, v.mora_estimada) == (
        vencido.id, "Ana Pérez", "TAL-001", 2, 75_000)
    assert (m.mora_facturada, m.mora_cobrada, m.tasa_retraso) == (75_000, 30_000, 0.5)


def test_tasa_retraso_sin_devoluciones_es_cero(session, admin):
    m = svc.morosidad(session, admin, factor_mora=1.5, hoy=HOY)
    assert (m.vencidos, m.mora_facturada, m.mora_cobrada, m.tasa_retraso) == ([], 0, 0, 0.0)


def test_empleado_no_ve_reportes(session, empleado):
    with pytest.raises(PermisoDenegado):
        svc.ingresos(session, empleado, *MARZO)
    with pytest.raises(PermisoDenegado):
        svc.morosidad(session, empleado, factor_mora=1.5, hoy=HOY)
