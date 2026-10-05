"""Predicción de demanda por categoría (spec §6.1)."""

from datetime import date

import pytest

from alquiler.ai import demanda
from alquiler.errors import PermisoDenegado
from alquiler.models import Categoria, EstadoAlquiler, Nivel
from tests.ai.conftest import alquilar


def _mes(anio, mes):
    return date(anio, mes, 1)


def _historial_estacional(session, cliente, equipo, meses=24, hasta=(2026, 10)):
    """`meses` meses terminando en `hasta`: 10 alquileres/mes y 25 en diciembre."""
    anio, mes = hasta
    for _ in range(meses):
        n = 25 if mes == 12 else 10
        for d in range(n):
            alquilar(session, cliente, equipo, date(anio, mes, 1 + d % 27), dias=1)
        anio, mes = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    session.commit()


def test_pico_de_diciembre_detectado(session, admin, cliente, equipo):
    _historial_estacional(session, cliente, equipo)
    [r] = demanda.predecir_demanda(session, admin, hoy=date(2026, 11, 15))
    assert "diciembre" in r.indicadores["picos"]
    assert 20 <= r.valor <= 30
    assert r.indicadores["mes_objetivo"] == "2026-12"
    assert r.confianza is Nivel.ALTA


def test_historial_corto_confianza_baja_e_indice_neutro(session, admin, cliente, equipo):
    for m in (7, 8, 9, 10):
        alquilar(session, cliente, equipo, date(2026, m, 3), dias=1)
    session.commit()
    [r] = demanda.predecir_demanda(session, admin, hoy=date(2026, 11, 15))
    assert r.confianza is Nivel.BAJA
    assert r.indicadores["indice_estacional"] == [1.0] * 12
    assert r.indicadores["meses_historial"] == 4


def test_categoria_sin_alquileres(session, admin, equipo):
    session.add(Categoria(nombre="Andamios"))
    session.commit()
    resultados = {r.indicadores["categoria"]: r for r in
                  demanda.predecir_demanda(session, admin, hoy=date(2026, 11, 15))}
    assert resultados["Andamios"].valor is None
    assert resultados["Andamios"].confianza is Nivel.BAJA
    assert "sin historial" in resultados["Andamios"].resumen.lower()


def test_rango_contiene_pronostico_y_no_es_negativo(session, admin, cliente, equipo):
    for i, m in enumerate(range(1, 11)):
        for _ in range(1 + (i % 3) * 4):  # serie irregular: 1, 5, 9, 1, 5, ...
            alquilar(session, cliente, equipo, date(2026, m, 2), dias=1)
    session.commit()
    [r] = demanda.predecir_demanda(session, admin, hoy=date(2026, 11, 15))
    minimo, maximo = r.indicadores["rango"]
    assert 0 <= minimo <= r.valor <= maximo


def test_cancelados_no_cuentan(session, admin, cliente, equipo):
    alquilar(session, cliente, equipo, date(2026, 10, 2), dias=1)
    alquilar(session, cliente, equipo, date(2026, 10, 3), dias=1, estado=EstadoAlquiler.CANCELADO)
    session.commit()
    assert demanda.serie_mensual(session, equipo.categoria_id, _mes(2026, 10)) == [
        (_mes(2026, 10), 1)]


def test_serie_incluye_meses_en_cero(session, cliente, equipo):
    alquilar(session, cliente, equipo, date(2026, 7, 2), dias=1)
    alquilar(session, cliente, equipo, date(2026, 9, 2), dias=1)
    session.commit()
    assert demanda.serie_mensual(session, equipo.categoria_id, _mes(2026, 10)) == [
        (_mes(2026, 7), 1), (_mes(2026, 8), 0), (_mes(2026, 9), 1), (_mes(2026, 10), 0)]


def test_resultado_siempre_explicado(session, admin, cliente, equipo):
    _historial_estacional(session, cliente, equipo, meses=8)
    for r in demanda.predecir_demanda(session, admin, hoy=date(2026, 11, 15)):
        assert r.justificacion and all(isinstance(j, str) and j for j in r.justificacion)
        assert "Estimación" in r.advertencia
        assert "≈" in r.resumen


def test_cliente_no_accede(session, usuario_cliente):
    with pytest.raises(PermisoDenegado):
        demanda.predecir_demanda(session, usuario_cliente)


def test_rango_nunca_es_un_punto(session, admin, cliente, equipo):
    # Una serie perfectamente regular da error histórico 0; aun así la estimación
    # no puede presentarse como certeza: el conteo de alquileres tiene ruido propio.
    _historial_estacional(session, cliente, equipo)
    [r] = demanda.predecir_demanda(session, admin, hoy=date(2026, 11, 15))
    minimo, maximo = r.indicadores["rango"]
    assert maximo - minimo >= 2 * 1.28 * r.valor ** 0.5 - 0.1
