"""Integración de punta a punta: todas las vistas, datos demo, rollback y cancelaciones."""

import pytest
from sqlalchemy import func, select

from alquiler.models import Alquiler, Devolucion, Equipo, Pago
from alquiler.seed import cargar_demo
from alquiler.services import alquileres as svc_alquileres
from alquiler.ui import app, trabajador, widgets
from alquiler.ui.logica.contexto import iniciar_sesion
from alquiler.ui.logica.navegacion import SECCIONES
from alquiler.ui.ventana import VentanaPrincipal
from tests.ui.conftest import HOY


@pytest.fixture
def errores(monkeypatch):
    registrados = []
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, msg: registrados.append(msg))
    monkeypatch.setattr(widgets, "informar", lambda parent, msg: None)
    monkeypatch.setattr(widgets, "confirmar", lambda parent, texto: True)
    return registrados


@pytest.fixture
def demo(fabrica, config):
    cargar_demo(config.db_path, HOY, config.admin_password, meses=4)
    return fabrica


def _recorrer(qtbot, ventana):
    for clave in ventana.claves_visibles():
        ventana.ir_a(clave)
        for _ in range(10):
            trabajador.esperar_tareas(500)
            qtbot.wait(20)
        assert "construcción" not in getattr(ventana.vista_actual(), "text", lambda: "")()


def test_todas_las_secciones_tienen_vista():
    assert set(app.fabricas_de_vistas()) == {s.clave for s in SECCIONES}


@pytest.mark.parametrize("usuario,clave", [("admin", "admin1234"), ("empleado", "empleado123"),
                                           ("cliente", "cliente123")])
def test_recorrido_completo_con_datos_demo(qtbot, demo, config, errores, usuario, clave):
    ctx = iniciar_sesion(demo, config, usuario, clave, reloj=lambda: HOY)
    ventana = VentanaPrincipal(ctx, app.fabricas_de_vistas())
    qtbot.addWidget(ventana)
    _recorrer(qtbot, ventana)
    assert errores == []
    ventana.ir_a("equipos")
    assert ventana.vista_actual().tabla.filas_mostradas() > 0


def test_base_vacia_todas_las_vistas_abren(qtbot, ctx_factory, errores):
    ventana = VentanaPrincipal(ctx_factory("admin"), app.fabricas_de_vistas())
    qtbot.addWidget(ventana)
    _recorrer(qtbot, ventana)
    assert errores == []


def _contar(fabrica, modelo):
    with fabrica() as s:
        return s.scalar(select(func.count()).select_from(modelo))


def test_rollback_de_punta_a_punta(qtbot, monkeypatch, ctx_factory, datos_base, fabrica, errores):
    """Un fallo a mitad de una operación lanzada desde la interfaz no deja escrituras."""
    from alquiler.ui.logica import operaciones, personas
    from alquiler.ui.vistas.alquileres import VistaAlquileres

    ctx = ctx_factory("empleado")
    operaciones.crear_alquiler(ctx, personas.clientes(ctx)[0]["id"],
                               operaciones.equipos_disponibles(ctx)[0]["id"], HOY, HOY)
    original = svc_alquileres.registrar_pago

    def pago_que_falla_a_medias(s, actor, alquiler_id, monto, metodo, concepto, hoy=None):
        s.add(Pago(alquiler_id=alquiler_id, monto=monto, fecha=hoy, metodo=metodo,
                   concepto=concepto))
        s.flush()                                  # el INSERT ya se ejecutó…
        raise RuntimeError("se cayó el disco")     # …y la operación falla

    monkeypatch.setattr(svc_alquileres, "registrar_pago", pago_que_falla_a_medias)
    monkeypatch.setattr(widgets, "ejecutar_dialogo", lambda dlg: True)
    vista = VistaAlquileres(ctx)
    qtbot.addWidget(vista)
    vista.tabla.selectRow(0)
    vista.botones["pago"].click()
    assert errores == ["Error inesperado: RuntimeError: se cayó el disco"]
    assert _contar(fabrica, Pago) == 0             # rollback: nada quedó escrito

    monkeypatch.setattr(svc_alquileres, "registrar_pago", original)
    vista.tabla.selectRow(0)
    vista.botones["pago"].click()                  # la siguiente operación funciona
    assert len(errores) == 1 and _contar(fabrica, Pago) == 1


def test_cancelar_dialogos_no_escribe(qtbot, monkeypatch, ctx_factory, datos_base, fabrica,
                                      errores):
    from alquiler.ui.logica import operaciones, personas
    from alquiler.ui.vistas.alquileres import VistaAlquileres
    from alquiler.ui.vistas.equipos import VistaEquipos

    ctx = ctx_factory("empleado")
    operaciones.crear_alquiler(ctx, personas.clientes(ctx)[0]["id"],
                               operaciones.equipos_disponibles(ctx)[0]["id"], HOY, HOY)
    antes = [_contar(fabrica, m) for m in (Alquiler, Devolucion, Pago, Equipo)]
    monkeypatch.setattr(widgets, "ejecutar_dialogo", lambda dlg: False)  # el usuario cancela
    alquileres, equipos = VistaAlquileres(ctx), VistaEquipos(ctx)
    qtbot.addWidget(alquileres)
    qtbot.addWidget(equipos)
    alquileres.botones["nuevo"].click()
    alquileres.tabla.selectRow(0)
    alquileres.botones["devolucion"].click()
    alquileres.tabla.selectRow(0)
    alquileres.botones["pago"].click()
    equipos.botones["nuevo"].click()
    assert errores == []
    assert [_contar(fabrica, m) for m in (Alquiler, Devolucion, Pago, Equipo)] == antes


def test_volver_a_una_seccion_muestra_datos_actuales(qtbot, ctx_factory, datos_base, errores):
    from datetime import date
    from alquiler.ui.logica import catalogo
    ctx = ctx_factory("admin")
    ventana = VentanaPrincipal(ctx, app.fabricas_de_vistas())
    qtbot.addWidget(ventana)
    ventana.ir_a("mantenimiento")
    assert ventana.vista_actual().combo_equipo.count() == 2
    ventana.ir_a("equipos")
    assert ventana.vista_actual().tabla.filas_mostradas() == 2
    cat = catalogo.categorias(ctx)[0]["id"]
    catalogo.crear_equipo(ctx, "TAL-003", "Nuevo", cat, 1_000, date(2025, 1, 1))  # otra pantalla
    ventana.ir_a("clientes")
    ventana.ir_a("equipos")
    assert ventana.vista_actual().tabla.filas_mostradas() == 3
    ventana.ir_a("mantenimiento")
    assert ventana.vista_actual().combo_equipo.count() == 3


def test_nuevo_alquiler_sin_equipos_o_clientes_avisa(qtbot, monkeypatch, ctx_factory, datos_base,
                                                     errores):
    from alquiler.ui.logica import catalogo, personas
    from alquiler.ui.vistas.alquileres import VistaAlquileres
    abiertos = []
    monkeypatch.setattr(widgets, "ejecutar_dialogo", lambda dlg: abiertos.append(dlg) or False)
    ctx = ctx_factory("admin")
    for e in catalogo.equipos(ctx):
        catalogo.dar_de_baja(ctx, e["id"])
    vista = VistaAlquileres(ctx)
    qtbot.addWidget(vista)
    vista.botones["nuevo"].click()
    assert errores == ["No hay equipos disponibles para alquilar."] and abiertos == []
    personas.desactivar_cliente(ctx, personas.clientes(ctx)[0]["id"])
    vista.botones["nuevo"].click()
    assert errores[-1] == "No hay clientes activos registrados." and abiertos == []
