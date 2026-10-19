"""Pantalla de Inicio: primera sección, tarjetas por rol, navegación y recarga."""

import pytest

from alquiler.errors import ReglaNegocioError
from alquiler.ui import app, widgets
from alquiler.ui.logica import catalogo, inicio
from alquiler.ui.logica.navegacion import secciones_para
from alquiler.ui.ventana import VentanaPrincipal
from alquiler.ui.vistas.inicio import VistaInicio


def _esperar(qtbot, vista):
    qtbot.waitUntil(lambda: not vista.ocupado, timeout=5000)


def _ventana(qtbot, ctx):
    v = VentanaPrincipal(ctx, app.fabricas_de_vistas())
    qtbot.addWidget(v)
    _esperar(qtbot, v.vista_actual())
    return v


@pytest.mark.parametrize("rol", ["admin", "empleado", "cliente"])
def test_inicio_es_la_primera_seccion(ctx_factory, rol):
    assert secciones_para(ctx_factory(rol))[0].clave == "inicio"


def test_ventana_abre_en_inicio(qtbot, ctx_factory, datos_base):
    v = _ventana(qtbot, ctx_factory("admin"))
    assert v.clave_actual() == "inicio" and isinstance(v.vista_actual(), VistaInicio)
    assert len(app.fabricas_de_vistas()) == 11


def test_vista_admin(qtbot, ctx_factory, datos_base):
    vista = VistaInicio(ctx_factory("admin"))
    qtbot.addWidget(vista)
    _esperar(qtbot, vista)
    assert vista.etiqueta_saludo.text().endswith(", Admin")
    assert len(vista.tarjetas) == 7
    assert vista.grafico_flota.segmentos()[0][:2] == ("Disponible", 2)
    assert vista.panel_alerta is not None and vista.boton_ver_analisis is not None


def test_vista_cliente(qtbot, ctx_factory, datos_base):
    vista = VistaInicio(ctx_factory("cliente"))
    qtbot.addWidget(vista)
    _esperar(qtbot, vista)
    assert vista.grafico_flota is None and vista.panel_alerta is None
    assert vista.grafico_tendencia is None and vista.tabla_monitor is None
    assert [t.etiqueta_titulo.text() for t in vista.tarjetas] == [
        "Mis alquileres activos", "Saldo pendiente"]


def test_clic_tarjeta_navega(qtbot, ctx_factory, datos_base):
    v = _ventana(qtbot, ctx_factory("admin"))
    [tarjeta] = [t for t in v.vista_actual().tarjetas if t.destino == "alquileres"][:1]
    tarjeta.activada.emit(tarjeta.destino)
    assert v.clave_actual() == "alquileres"


def test_ver_analisis_navega(qtbot, ctx_factory, datos_base):
    v = _ventana(qtbot, ctx_factory("admin"))
    v.vista_actual().boton_ver_analisis.click()
    assert v.clave_actual() == "analisis_ia"


def test_recarga_al_volver(qtbot, ctx_factory, datos_base):
    ctx = ctx_factory("admin")
    vista = VistaInicio(ctx)
    qtbot.addWidget(vista)
    _esperar(qtbot, vista)
    antes = sum(n for _, n, _ in vista.grafico_flota.segmentos())
    catalogo.crear_equipo(ctx, "TAL-009", "Taladro nuevo", catalogo.categorias(ctx)[0]["id"],
                          20_000, ctx.hoy())
    vista.al_volver()
    _esperar(qtbot, vista)
    assert sum(n for _, n, _ in vista.grafico_flota.segmentos()) == antes + 1


def test_error_se_muestra(qtbot, ctx_factory, monkeypatch):
    mensajes = []
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, m: mensajes.append(m))

    def falla(ctx, **_):
        raise ReglaNegocioError("x")

    monkeypatch.setattr(inicio, "resumen", falla)
    vista = VistaInicio(ctx_factory("admin"))
    qtbot.addWidget(vista)
    _esperar(qtbot, vista)
    assert mensajes == ["x"] and vista.tarjetas == []


def test_cliente_tiene_accesos(qtbot, ctx_factory, datos_base):
    v = _ventana(qtbot, ctx_factory("cliente"))
    vista = v.vista_actual()
    assert set(vista.botones_acceso) == {"equipos", "perfil"}
    vista.botones_acceso["perfil"].click()
    assert v.clave_actual() == "perfil"


def test_atributos_existen_antes_de_cargar(qtbot, ctx_factory, monkeypatch):
    monkeypatch.setattr(inicio, "resumen", lambda ctx, **_: (_ for _ in ()).throw(ReglaNegocioError("x")))
    monkeypatch.setattr(widgets, "mostrar_error", lambda parent, m: None)
    vista = VistaInicio(ctx_factory("admin"))
    qtbot.addWidget(vista)
    _esperar(qtbot, vista)
    assert vista.botones_acceso == {} and vista.tarjetas == []


def test_tablero_del_centro_de_control(qtbot, ctx_factory, datos_base, fabrica):
    from datetime import date
    from alquiler.models import Alquiler, Cliente, Equipo, EstadoAlquiler, EstadoEquipo
    with fabrica() as s:  # un alquiler vencido para que el monitor tenga actividad
        equipo = s.query(Equipo).filter_by(codigo="TAL-001").one()
        equipo.estado = EstadoEquipo.ALQUILADO
        s.add(Alquiler(cliente=s.query(Cliente).first(), equipo=equipo, fecha_inicio=date(2026, 3, 1),
                       fecha_fin_prevista=date(2026, 3, 8), tarifa_diaria=25_000, costo_estimado=175_000,
                       estado=EstadoAlquiler.ACTIVO))
        s.commit()
    vista = VistaInicio(ctx_factory("admin"))
    qtbot.addWidget(vista)
    _esperar(qtbot, vista)
    assert vista.etiqueta_titulo.text() == "Tablero de control"
    assert (vista.grafico_flota.texto_centro, vista.grafico_flota.subtexto_centro) == (
        "50 %", "Utilización total")
    assert [n for n, _ in vista.grafico_tendencia.series_datos()] == ["Iniciados", "Devueltos"]
    assert vista.grafico_tendencia.series_datos()[0][1][-1] == 1  # marzo: un alquiler iniciado
    assert [b.value() for b in vista.barras_categoria] == [50]
    assert vista.tabla_monitor.filas_mostradas() == 1
    assert vista.tabla_monitor.texto(0, 3) == "VENCIDO"
    assert all(t.etiqueta_icono is not None for t in vista.tarjetas)


def test_tablero_animado_termina_en_los_valores_reales(qtbot, ctx_factory, datos_base, monkeypatch):
    """Con animaciones: las cifras cuentan y las barras se llenan, pero acaban en el dato exacto."""
    from alquiler.ui import animacion
    monkeypatch.setattr(animacion, "_forzado", True)
    ctx = ctx_factory("admin")
    esperadas = [str(d["valor"]) for d in inicio.tarjetas_kpi(inicio.resumen(ctx), {
        s.clave for s in secciones_para(ctx)})]
    vista = VistaInicio(ctx)
    qtbot.addWidget(vista)
    vista.show()
    _esperar(qtbot, vista)
    qtbot.waitUntil(lambda: [t.etiqueta_valor.text() for t in vista.tarjetas] == esperadas,
                    timeout=4000)
    assert vista.animaciones  # la vista guarda sus animaciones en curso
