"""Reportes: datos planos para la vista y generación en segundo plano."""

from datetime import date, timedelta

import pytest

from alquiler.ui import widgets
from alquiler.ui.logica import operaciones, personas
from alquiler.ui.logica import reportes as logica
from alquiler.ui.vistas.reportes import VistaReportes
from tests.ui.conftest import HOY


@pytest.fixture
def con_movimientos(ctx_factory, datos_base):
    """Un alquiler pagado este mes y uno vencido (sin devolver)."""
    emp = ctx_factory("empleado")
    cliente = personas.clientes(emp)[0]["id"]
    equipos = operaciones.equipos_disponibles(emp)
    a = operaciones.crear_alquiler(emp, cliente, equipos[0]["id"], HOY, HOY + timedelta(days=2))
    operaciones.registrar_pago(emp, a, 50_000, "efectivo", "alquiler")
    return ctx_factory("admin")


def test_generar_reporte_plano(con_movimientos):
    r = logica.generar(con_movimientos, date(2026, 1, 1), HOY)
    assert dict(r["kpis"])["Ingresos del período"] == "$50.000"
    # marzo está en curso (hasta = 10/03): se marca para que no parezca una caída
    assert r["ingresos_mes"] == [("ene 2026", 0), ("feb 2026", 0), ("mar 2026*", 50_000)]
    completo = logica.generar(con_movimientos, date(2026, 1, 1), date(2026, 2, 28))
    assert [m for m, _ in completo["ingresos_mes"]] == ["ene 2026", "feb 2026"]
    assert [u["codigo"] for u in r["uso_equipos"]][0] == "TAL-001"
    assert r["uso_categorias"][0][0] == "Taladros"
    assert r["vencidos"] == []


def test_periodo_invertido(con_movimientos):
    from alquiler.errors import ReglaNegocioError
    with pytest.raises(ReglaNegocioError, match="período"):
        logica.generar(con_movimientos, HOY, date(2026, 1, 1))


def test_vista_reportes_genera_en_segundo_plano(qtbot, con_movimientos):
    v = VistaReportes(con_movimientos)
    qtbot.addWidget(v)
    assert not v.boton_generar.isEnabled()          # la primera carga ya está en curso
    qtbot.waitUntil(v.boton_generar.isEnabled, timeout=5000)
    [serie] = v.grafico_ingresos.chart().series()
    assert serie.barSets()[0].count() == 6           # seis meses por defecto
    assert v.kpis["Ingresos del período"].text() == "$50.000"
    assert v.tabla_uso.filas_mostradas() == 2
    assert v.grafico_categorias.chart().series()


def test_periodo_invertido_muestra_error(qtbot, monkeypatch, con_movimientos):
    errores = []
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, msg: errores.append(msg))
    v = VistaReportes(con_movimientos)
    qtbot.addWidget(v)
    qtbot.waitUntil(v.boton_generar.isEnabled, timeout=5000)
    v.campo_desde.setDate(HOY)
    v.campo_hasta.setDate(date(2026, 1, 1))
    v.boton_generar.click()
    qtbot.waitUntil(lambda: bool(errores), timeout=5000)
    assert "período" in errores[0] and v.boton_generar.isEnabled()
