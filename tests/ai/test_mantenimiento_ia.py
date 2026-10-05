"""Recomendador de mantenimiento preventivo (spec §6.2)."""

from datetime import date, timedelta

import pytest

from alquiler.ai import mantenimiento as ia
from alquiler.models import (
    Equipo,
    EstadoEquipo,
    Mantenimiento,
    Nivel,
    RecomendacionIA,
    TipoMantenimiento,
    TipoRecomendacion,
)
from tests.ai.conftest import HOY, alquilar


def _correctivo(session, equipo, hace_dias, usos=0, cerrado=True):
    inicio = HOY - timedelta(days=hace_dias)
    session.add(Mantenimiento(equipo=equipo, tipo=TipoMantenimiento.CORRECTIVO,
                              fecha_inicio=inicio, fecha_fin=inicio + timedelta(days=1) if cerrado else None,
                              descripcion="Falla", usos_al_momento=usos))


@pytest.fixture
def desgastado(session, cliente, equipo):
    """25 usos sin servicio desde hace ~200 días, 2 fallas en el año y uso reciente."""
    equipo.usos_acumulados = 25
    equipo.fecha_adquisicion = HOY - timedelta(days=700)
    _correctivo(session, equipo, 300)
    _correctivo(session, equipo, 200)
    for d in (5, 15, 25):
        alquilar(session, cliente, equipo, HOY - timedelta(days=d), dias=1)
    session.commit()
    return equipo


@pytest.fixture
def nuevo(session, categoria):
    e = Equipo(codigo="TAL-NEW", nombre="Taladro nuevo", categoria=categoria, tarifa_diaria=1,
               fecha_adquisicion=HOY - timedelta(days=10))
    session.add(e)
    session.commit()
    return e


def test_equipo_desgastado_prioridad_alta(desgastado):
    r = ia.evaluar_equipo(desgastado, HOY, max_alquileres_30d=3)
    assert r.valor >= 75
    assert r.indicadores["prioridad"] == "alta"
    assert r.indicadores["fallas_12m"] == 2


def test_equipo_nuevo_no_genera_alerta(session, admin, desgastado, nuevo):
    codigos = [r.indicadores["codigo"] for r in ia.recomendar_mantenimiento(session, admin, hoy=HOY)]
    assert codigos == ["TAL-001"]


def test_puntaje_desglosado_suma_el_total(desgastado, nuevo):
    for equipo in (desgastado, nuevo):
        r = ia.evaluar_equipo(equipo, HOY, max_alquileres_30d=3)
        assert abs(sum(r.indicadores["aporte_puntos"].values()) - r.valor) < 0.01


def test_factor_recortado_a_1(session, equipo):
    equipo.usos_acumulados = 100
    session.commit()
    r = ia.evaluar_equipo(equipo, HOY, max_alquileres_30d=0)
    assert r.indicadores["aporte_puntos"]["usos_desde_servicio"] == 35.0


def test_servicio_reciente_reinicia_contadores(session, equipo):
    equipo.usos_acumulados = 40
    session.add(Mantenimiento(equipo=equipo, tipo=TipoMantenimiento.PREVENTIVO,
                              fecha_inicio=HOY - timedelta(days=2), fecha_fin=HOY - timedelta(days=1),
                              descripcion="Preventivo", usos_al_momento=40))
    session.commit()
    aportes = ia.evaluar_equipo(equipo, HOY, max_alquileres_30d=0).indicadores["aporte_puntos"]
    assert aportes["usos_desde_servicio"] == 0
    assert aportes["dias_desde_servicio"] < 0.5


def test_mantenimiento_abierto_no_cuenta_como_servicio(session, equipo):
    equipo.usos_acumulados = 30
    _correctivo(session, equipo, 3, usos=30, cerrado=False)
    session.commit()
    aportes = ia.evaluar_equipo(equipo, HOY, max_alquileres_30d=0).indicadores["aporte_puntos"]
    assert aportes["usos_desde_servicio"] == 35.0


def test_excluye_fuera_de_servicio_y_en_mantenimiento(session, admin, desgastado):
    for estado in (EstadoEquipo.FUERA_DE_SERVICIO, EstadoEquipo.EN_MANTENIMIENTO):
        desgastado.estado = estado
        session.commit()
        assert ia.recomendar_mantenimiento(session, admin, hoy=HOY, persistir=False) == []


def test_persiste_sin_duplicar(session, admin, desgastado):
    ia.recomendar_mantenimiento(session, admin, hoy=HOY)
    ia.recomendar_mantenimiento(session, admin, hoy=HOY)
    [rec] = session.query(RecomendacionIA).filter_by(tipo=TipoRecomendacion.MANTENIMIENTO).all()
    assert rec.equipo_id == desgastado.id and rec.prioridad is Nivel.ALTA
    assert rec.justificacion and rec.datos_respaldo["usos_desde_servicio"] == 25


def test_confianza_baja_con_pocos_alquileres(session, equipo):
    equipo.usos_acumulados = 30
    session.commit()
    assert ia.evaluar_equipo(equipo, HOY, max_alquileres_30d=0).confianza is Nivel.BAJA


def test_justificacion_legible_y_advertencia(desgastado):
    r = ia.evaluar_equipo(desgastado, HOY, max_alquileres_30d=3)
    assert any("Usos desde el último servicio: 25/20" in j for j in r.justificacion)
    assert "Estimación" in r.advertencia
