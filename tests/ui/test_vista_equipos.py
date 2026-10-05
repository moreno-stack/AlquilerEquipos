"""Vistas de equipos (catálogo + máquina de estados visual) y de mantenimiento."""

from datetime import date

import pytest
from sqlalchemy import func, select

from alquiler.models import Equipo, EstadoEquipo
from alquiler.ui import widgets
from alquiler.ui.logica import catalogo
from alquiler.ui.vistas.equipos import DialogoEquipo, VistaEquipos
from alquiler.ui.vistas.mantenimiento import DialogoCierre, VistaMantenimiento


@pytest.fixture
def errores(monkeypatch):
    registrados = []
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, msg: registrados.append(msg))
    monkeypatch.setattr(widgets, "confirmar", lambda parent, texto: True)
    return registrados


def _dialogos(monkeypatch, rellenar, aceptar=True):
    """Sustituye la ejecución modal: rellena el diálogo y lo acepta o cancela."""
    def ejecutar(dlg):
        rellenar(dlg)
        return aceptar
    monkeypatch.setattr(widgets, "ejecutar_dialogo", ejecutar)


def _contar_equipos(fabrica):
    with fabrica() as s:
        return s.scalar(select(func.count()).select_from(Equipo))


def test_vista_equipos_cliente_solo_lectura(qtbot, ctx_factory, datos_base, fabrica):
    with fabrica() as s:
        s.scalar(select(Equipo).where(Equipo.codigo == "TAL-002")).estado = EstadoEquipo.EN_MANTENIMIENTO
        s.commit()
    v = VistaEquipos(ctx_factory("cliente"))
    qtbot.addWidget(v)
    assert v.botones == {}
    assert v.combo_estado.isHidden()
    assert v.tabla.filas_mostradas() == 1 and v.tabla.texto(0, 0) == "TAL-001"


def test_filtro_por_texto_y_estado(qtbot, ctx_factory, datos_base):
    v = VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(v)
    assert v.tabla.filas_mostradas() == 2
    v.campo_buscar.setText("inalámbrico")
    assert v.tabla.filas_mostradas() == 1
    v.campo_buscar.clear()
    v.combo_estado.setCurrentText("Alquilado")
    assert v.tabla.filas_mostradas() == 0


def test_panel_estados_al_seleccionar(qtbot, ctx_factory, datos_base):
    v = VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(v)
    assert v.panel_estados.estado_actual is None
    v.tabla.selectRow(0)
    assert v.panel_estados.estado_actual == "Disponible"
    assert v.panel_estados.alcanzables == catalogo.estados_posibles("Disponible")
    assert v.panel_estados.insignias["Disponible"].tono == "ok"
    assert v.panel_estados.insignias["Fuera de servicio"].tono == "info"  # alcanzable


def test_nuevo_equipo_desde_dialogo(qtbot, monkeypatch, ctx_factory, datos_base, errores):
    def rellenar(dlg: DialogoEquipo):
        dlg.campo_codigo.setText("TAL-003")
        dlg.campo_nombre.setText("Rotomartillo")
        dlg.campo_tarifa.setValue(35_000)
    _dialogos(monkeypatch, rellenar)
    v = VistaEquipos(ctx_factory("empleado"))
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    assert errores == [] and v.tabla.filas_mostradas() == 3


def test_cancelar_dialogo_no_escribe(qtbot, monkeypatch, ctx_factory, datos_base, fabrica, errores):
    _dialogos(monkeypatch, lambda dlg: dlg.campo_codigo.setText("TAL-009"), aceptar=False)
    v = VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    assert _contar_equipos(fabrica) == 2 and v.tabla.filas_mostradas() == 2


def test_error_se_muestra_y_tabla_intacta(qtbot, monkeypatch, ctx_factory, datos_base, errores):
    def rellenar(dlg):
        dlg.campo_codigo.setText("tal-001")
        dlg.campo_nombre.setText("Duplicado")
    _dialogos(monkeypatch, rellenar)
    v = VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(v)
    v.botones["nuevo"].click()
    assert len(errores) == 1 and "TAL-001" in errores[0]
    assert v.tabla.filas_mostradas() == 2


def test_editar_sin_seleccion_avisa(qtbot, ctx_factory, datos_base, errores):
    v = VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(v)
    v.botones["editar"].click()
    assert errores == ["Seleccione un equipo de la tabla."]


def test_editar_tarifa(qtbot, monkeypatch, ctx_factory, datos_base, errores):
    _dialogos(monkeypatch, lambda dlg: dlg.campo_tarifa.setValue(27_000))
    v = VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(v)
    v.tabla.selectRow(0)
    v.botones["editar"].click()
    assert errores == [] and v.tabla.texto(0, 4) == "$27.000"


def test_empleado_no_ve_eliminar_y_admin_si(qtbot, ctx_factory, datos_base):
    emp, adm = VistaEquipos(ctx_factory("empleado")), VistaEquipos(ctx_factory("admin"))
    qtbot.addWidget(emp)
    qtbot.addWidget(adm)
    assert "eliminar" not in emp.botones and "eliminar" in adm.botones
    assert "baja" in emp.botones and "mantenimiento" in emp.botones


def test_dar_de_baja_con_confirmacion(qtbot, ctx_factory, datos_base, errores):
    v = VistaEquipos(ctx_factory("empleado"))
    qtbot.addWidget(v)
    v.tabla.selectRow(0)
    v.botones["baja"].click()
    assert errores == [] and v.tabla.texto(0, 3) == "Fuera de servicio"


def test_abrir_y_cerrar_mantenimiento_desde_vistas(qtbot, monkeypatch, ctx_factory, datos_base,
                                                   errores):
    ctx = ctx_factory("empleado")
    equipos_v = VistaEquipos(ctx)
    qtbot.addWidget(equipos_v)
    equipos_v.tabla.selectRow(0)
    _dialogos(monkeypatch, lambda dlg: dlg.campo_descripcion.setPlainText("Revisión de motor"))
    equipos_v.botones["mantenimiento"].click()
    assert errores == [] and equipos_v.tabla.texto(0, 3) == "En mantenimiento"

    vista = VistaMantenimiento(ctx)
    qtbot.addWidget(vista)
    assert vista.tabla_abiertos.filas_mostradas() == 1

    def cerrar(dlg: DialogoCierre):
        dlg.campo_costo.setValue(50_000)
        dlg.campo_notas.setPlainText("Escobillas nuevas")
    _dialogos(monkeypatch, cerrar)
    vista.tabla_abiertos.selectRow(0)
    vista.boton_cerrar.click()
    assert errores == [] and vista.tabla_abiertos.filas_mostradas() == 0
    vista.combo_equipo.setCurrentIndex(vista.combo_equipo.findText("TAL-001", widgets.Qt.MatchFlag.MatchStartsWith))
    assert vista.tabla_historial.filas_mostradas() == 1
    assert vista.tabla_historial.texto(0, 3) == "$50.000"


def test_dialogo_equipo_limita_fecha_y_tarifa(qtbot, ctx_factory, datos_base):
    dlg = DialogoEquipo(catalogo.categorias(ctx_factory("admin")), hoy=date(2026, 3, 10))
    qtbot.addWidget(dlg)
    assert dlg.campo_fecha.maximumDate().toPython() == date(2026, 3, 10)
    assert dlg.campo_tarifa.minimum() == 1 and dlg.campo_tarifa.maximum() == 100_000_000
