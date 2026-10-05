"""Análisis de patrones de retraso (spec §6.3)."""

from datetime import date, timedelta

import pytest

from alquiler.ai import retrasos as ia
from alquiler.errors import PermisoDenegado
from alquiler.models import (
    Categoria,
    Cliente,
    Equipo,
    Nivel,
    RecomendacionIA,
    TipoRecomendacion,
)
from tests.ai.conftest import alquilar

INICIO = date(2026, 1, 1)


def _cliente(session, doc, nombre):
    c = Cliente(documento=doc, nombre=nombre, telefono="3")
    session.add(c)
    return c


def _devoluciones(session, cliente, equipo, tardias, a_tiempo):
    for i in range(tardias + a_tiempo):
        alquilar(session, cliente, equipo, INICIO + timedelta(days=3 * i), dias=2,
                 retraso=3 if i < tardias else 0)


@pytest.fixture
def escenario(session, cliente, equipo):
    """Ana: 4/4 tardías. Otros: 16 a tiempo. Tasa global = 4/20 = 0,2."""
    _devoluciones(session, cliente, equipo, tardias=4, a_tiempo=0)
    _devoluciones(session, _cliente(session, "2", "Luis Gómez"), equipo, tardias=0, a_tiempo=16)
    session.commit()
    return cliente


def test_tasa_suavizada_formula():
    assert ia.tasa_suavizada(4, 4, 0.2) == pytest.approx((4 + 1) / 9)
    assert ia.tasa_suavizada(0, 0, 0.2) == pytest.approx(0.2)


def test_cliente_moroso_marcado(session, admin, escenario):
    a = ia.analizar_retrasos(session, admin, persistir=False)
    assert (a.tasa_global, a.n_devoluciones) == (pytest.approx(0.2), 20)
    [r] = a.clientes_marcados
    ind = r.indicadores
    assert (ind["cliente_id"], ind["n"], ind["retrasos"]) == (escenario.id, 4, 4)
    assert ind["tasa_suavizada"] > 0.4
    assert ind["tasa_observada"] == 1.0
    assert ind["dias_promedio_retraso"] == 3.0
    assert ind["categoria_mas_asociada"] == "Taladros"
    assert r.confianza is Nivel.BAJA  # n = 4 < 5


def test_un_solo_retraso_no_marca(session, admin, escenario, equipo):
    _devoluciones(session, _cliente(session, "3", "Eva"), equipo, tardias=1, a_tiempo=0)
    session.commit()
    marcados = [r.indicadores["cliente_id"] for r in
                ia.analizar_retrasos(session, admin, persistir=False).clientes_marcados]
    assert marcados == [escenario.id]


def test_sin_devoluciones(session, admin):
    a = ia.analizar_retrasos(session, admin)
    assert (a.tasa_global, a.n_devoluciones, a.clientes_marcados, a.por_categoria) == (0.0, 0, [], [])


def test_sin_retrasos_globales_no_marca_a_nadie(session, admin, cliente, equipo):
    _devoluciones(session, cliente, equipo, tardias=0, a_tiempo=10)
    session.commit()
    assert ia.analizar_retrasos(session, admin).clientes_marcados == []


def test_justificacion_explica_el_suavizado(session, admin, escenario):
    [r] = ia.analizar_retrasos(session, admin, persistir=False).clientes_marcados
    texto = " ".join(r.justificacion)
    assert "100,0 %" in texto and "55,6 %" in texto and "20,0 %" in texto
    assert "Estimación" in r.advertencia


def test_persiste_sin_duplicar(session, admin, escenario):
    ia.analizar_retrasos(session, admin)
    ia.analizar_retrasos(session, admin)
    [rec] = session.query(RecomendacionIA).filter_by(tipo=TipoRecomendacion.RETRASO).all()
    assert rec.cliente_id == escenario.id
    assert rec.puntaje == pytest.approx(100 * 5 / 9, abs=0.01)
    assert rec.datos_respaldo["retrasos"] == 4


def test_por_categoria_ordena_por_tasa(session, admin, escenario, equipo):
    andamios = Categoria(nombre="Andamios")
    otro = Equipo(codigo="AND-1", nombre="Andamio", categoria=andamios, tarifa_diaria=1,
                  fecha_adquisicion=date(2025, 1, 1))
    session.add(otro)
    _devoluciones(session, escenario, otro, tardias=0, a_tiempo=5)
    session.commit()
    nombres = [r.indicadores["categoria"] for r in
               ia.analizar_retrasos(session, admin, persistir=False).por_categoria]
    assert nombres == ["Taladros", "Andamios"]


def test_cliente_no_accede(session, usuario_cliente):
    with pytest.raises(PermisoDenegado):
        ia.analizar_retrasos(session, usuario_cliente)
