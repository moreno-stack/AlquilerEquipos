"""Alquileres, devoluciones, pagos y reservas: lógica de presentación y vistas."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from alquiler.models import Alquiler, Cliente, Equipo, EstadoAlquiler, Usuario
from alquiler.services import alquileres as svc
from alquiler.ui import widgets
from alquiler.ui.logica import catalogo, operaciones
from alquiler.ui.vistas.alquileres import (
    DialogoAlquiler,
    DialogoDevolucion,
    DialogoPago,
    VistaAlquileres,
)
from alquiler.ui.vistas.reservas import VistaReservas
from tests.ui.conftest import HOY

D = timedelta(days=1)


@pytest.fixture
def escenario(ctx_factory, datos_base, fabrica):
    """TAL-001 al día, TAL-002 vencido y tres reservas: pendiente, lista y vencida."""
    ctx = ctx_factory("empleado")
    cat = catalogo.categorias(ctx)[0]["id"]
    for codigo in ("RES-1", "RES-2", "RES-3", "LIB-1"):
        catalogo.crear_equipo(ctx, codigo, f"Equipo {codigo}", cat, 10_000, date(2025, 1, 1))
    with fabrica() as s:
        emp = s.scalar(select(Usuario).where(Usuario.username == "empleado"))
        cli = s.scalar(select(Cliente.id))
        eq = {e.codigo: e.id for e in s.scalars(select(Equipo))}
        s.add(Cliente(documento="2", nombre="Zoe Inactiva", telefono="3", activo=False))
        s.commit()
        svc.crear_alquiler(s, emp, cli, eq["TAL-001"], HOY, HOY + 3 * D, hoy=HOY)
        svc.crear_alquiler(s, emp, cli, eq["TAL-002"], HOY - 6 * D, HOY - 2 * D, hoy=HOY - 6 * D)
        svc.crear_alquiler(s, emp, cli, eq["RES-1"], HOY + 3 * D, HOY + 5 * D, hoy=HOY)
        svc.crear_alquiler(s, emp, cli, eq["RES-2"], HOY - D, HOY + 2 * D, hoy=HOY - 2 * D)
        svc.crear_alquiler(s, emp, cli, eq["RES-3"], HOY - 7 * D, HOY - 4 * D, hoy=HOY - 9 * D)
    return ctx


@pytest.fixture
def errores(monkeypatch):
    registrados = []
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, msg: registrados.append(msg))
    monkeypatch.setattr(widgets, "confirmar", lambda parent, texto: True)
    monkeypatch.setattr(widgets, "informar", lambda parent, msg: None)
    return registrados


def _dialogos(monkeypatch, rellenar, aceptar=True):
    monkeypatch.setattr(widgets, "ejecutar_dialogo", lambda dlg: (rellenar(dlg), aceptar)[1])


def _fila(vista, equipo):
    for i in range(vista.tabla.filas_mostradas()):
        if vista.tabla.texto(i, 1).startswith(equipo):
            vista.tabla.selectRow(i)
            return i
    raise AssertionError(f"{equipo} no está en la tabla")


# ---------------------------------------------------------------- lógica
def test_cotizar():
    assert operaciones.cotizar(HOY, HOY + 3 * D, 25_000) == {
        "dias": 3, "costo": 75_000, "texto": "3 días × $25.000 = $75.000"}
    assert operaciones.cotizar(HOY, HOY, 25_000)["texto"] == "1 día × $25.000 = $25.000"
    assert operaciones.cotizar(HOY, HOY - D, 25_000)["costo"] is None


def test_alquileres_con_situacion(escenario):
    filas = {f["equipo"].split(" ·")[0]: f for f in operaciones.alquileres(escenario)}
    assert set(filas) == {"TAL-001", "TAL-002"}  # por defecto, solo activos
    assert (filas["TAL-001"]["situacion"], filas["TAL-002"]["situacion"]) == ("al día", "vencido")
    assert filas["TAL-001"]["saldo"] == "$75.000"
    assert len(operaciones.alquileres(escenario, None)) == 5


def test_previsualizar_devolucion_con_mora(escenario):
    vencido = next(f for f in operaciones.alquileres(escenario) if f["situacion"] == "vencido")
    p = operaciones.previsualizar_devolucion(escenario, vencido["id"], HOY, 0)
    # 2 días × $30.000 × 1,5 = $90.000 de mora
    assert (p["dias_retraso"], p["mora"], p["total"]) == (2, 90_000, 120_000 + 90_000)
    assert "2 días de retraso" in p["texto"] and "$90.000" in p["texto"]


def test_reservas_clasificadas(escenario):
    situaciones = {f["equipo"].split(" ·")[0]: f["situacion"] for f in operaciones.reservas(escenario)}
    assert situaciones == {"RES-1": "pendiente", "RES-2": "lista para entregar",
                           "RES-3": "vencida"}


# ---------------------------------------------------------------- diálogos
def test_dialogo_alquiler_solo_habilitados_y_cotiza_en_vivo(qtbot, escenario):
    from alquiler.ui.logica import personas
    dlg = DialogoAlquiler(personas.clientes_habilitados(escenario),
                          operaciones.equipos_disponibles(escenario), HOY)
    qtbot.addWidget(dlg)
    clientes = [dlg.combo_cliente.itemText(i) for i in range(dlg.combo_cliente.count())]
    equipos = [dlg.combo_equipo.itemText(i) for i in range(dlg.combo_equipo.count())]
    assert clientes == ["Ana Pérez — 1085000001"]          # sin la inactiva
    assert [e.split(" ·")[0] for e in equipos] == ["LIB-1"]  # solo disponibles
    assert dlg.campo_inicio.minimumDate().toPython() == HOY
    dlg.campo_fin.setDate(HOY + 4 * D)
    assert dlg.etiqueta_cotizacion.text() == "4 días × $10.000 = $40.000"
    dlg.campo_inicio.setDate(HOY + 6 * D)                    # el fin se ajusta al nuevo mínimo
    assert dlg.campo_fin.date().toPython() == HOY + 6 * D


def test_guardar_dos_veces_acepta_una_sola_vez(qtbot, escenario):
    from alquiler.ui.logica import personas
    dlg = DialogoAlquiler(personas.clientes_habilitados(escenario),
                          operaciones.equipos_disponibles(escenario), HOY)
    qtbot.addWidget(dlg)
    aceptados = []
    dlg.accepted.connect(lambda: aceptados.append(1))
    dlg.boton_guardar.click()
    dlg.boton_guardar.click()
    assert aceptados == [1]


def test_fecha_devolucion_minima_es_el_inicio(qtbot):
    fila = {"id": 1, "equipo": "TAL-002", "cliente": "Ana", "inicio_valor": HOY - 6 * D}
    dlg = DialogoDevolucion(fila, HOY, lambda f, p: {"texto": "x"})
    qtbot.addWidget(dlg)
    assert dlg.campo_fecha.minimumDate().toPython() == HOY - 6 * D
    assert dlg.campo_fecha.maximumDate().toPython() == HOY
    assert not dlg.campo_penalizacion.isEnabled()
    dlg.casilla_danos.setChecked(True)
    assert dlg.campo_penalizacion.isEnabled() and dlg.campo_descripcion.isEnabled()


def test_pago_maximo_es_el_saldo(qtbot):
    dlg = DialogoPago({"id": 1, "equipo": "TAL-001", "cliente": "Ana"}, 75_000)
    qtbot.addWidget(dlg)
    assert dlg.campo_monto.maximum() == 75_000 and dlg.campo_monto.value() == 75_000
    assert "$75.000" in dlg.etiqueta_saldo.text()


# ---------------------------------------------------------------- vistas
def test_alquiler_vencido_resaltado(qtbot, escenario):
    v = VistaAlquileres(escenario)
    qtbot.addWidget(v)
    assert v.tabla.tono_fila(_fila(v, "TAL-002")) == "peligro"
    assert v.tabla.tono_fila(_fila(v, "TAL-001")) is None


def test_nuevo_alquiler_desde_vista(qtbot, monkeypatch, escenario, errores):
    _dialogos(monkeypatch, lambda dlg: dlg.campo_fin.setDate(HOY + 2 * D))
    v = VistaAlquileres(escenario)
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    assert errores == [] and v.tabla.filas_mostradas() == 3


def test_dialogo_devolucion_vista_previa_y_registro(qtbot, monkeypatch, escenario, errores):
    vistas_previas = []

    def rellenar(dlg: DialogoDevolucion):
        vistas_previas.append(dlg.etiqueta_vista_previa.text())
        dlg.campo_horas.setValue(12)
    _dialogos(monkeypatch, rellenar)
    v = VistaAlquileres(escenario)
    qtbot.addWidget(v)
    _fila(v, "TAL-002")
    v.botones["devolucion"].click()
    assert errores == [] and "mora $90.000" in vistas_previas[0]
    assert [v.tabla.texto(i, 1).split(" ·")[0] for i in range(v.tabla.filas_mostradas())] == ["TAL-001"]


def test_pago_desde_vista_y_sin_saldo(qtbot, monkeypatch, escenario, errores):
    _dialogos(monkeypatch, lambda dlg: None)  # acepta el saldo completo
    v = VistaAlquileres(escenario)
    qtbot.addWidget(v)
    i = _fila(v, "TAL-001")
    v.botones["pago"].click()
    assert errores == [] and v.tabla.texto(i, 6) == "$0"
    v.tabla.selectRow(i)
    v.botones["pago"].click()
    assert errores == ["El alquiler no tiene saldo pendiente."]


def test_cancelar_dialogo_de_alquiler_no_escribe(qtbot, monkeypatch, escenario, fabrica, errores):
    _dialogos(monkeypatch, lambda dlg: None, aceptar=False)
    v = VistaAlquileres(escenario)
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    with fabrica() as s:
        assert s.scalar(select(func.count()).select_from(Alquiler)) == 5


def test_vista_reservas_entrega_y_cancela(qtbot, escenario, errores):
    v = VistaReservas(escenario)
    qtbot.addWidget(v)
    assert v.tabla.filas_mostradas() == 3
    assert v.etiqueta_resumen.text() == "3 reservas · 1 vencida"
    _fila(v, "RES-2")
    v.botones["entregar"].click()
    _fila(v, "RES-1")
    v.botones["cancelar"].click()
    assert errores == [] and v.tabla.filas_mostradas() == 1
    estados = {f["equipo"].split(" ·")[0]: f["estado"] for f in operaciones.alquileres(escenario, None)}
    assert (estados["RES-2"], estados["RES-1"]) == ("activo", "cancelado")


def test_vencida_no_se_entrega_y_se_explica(qtbot, escenario, errores):
    v = VistaReservas(escenario)
    qtbot.addWidget(v)
    assert v.tabla.tono_fila(_fila(v, "RES-3")) == "peligro"
    v.botones["entregar"].click()
    assert len(errores) == 1 and "venció" in errores[0]
    assert v.tabla.filas_mostradas() == 3
