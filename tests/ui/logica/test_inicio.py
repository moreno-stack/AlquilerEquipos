"""Lógica de la pantalla de Inicio: indicadores por rol, sin Qt."""

from datetime import date, datetime

import pytest

from alquiler.models import (
    Alquiler,
    Cliente,
    ConceptoPago,
    Equipo,
    EstadoAlquiler,
    EstadoEquipo,
    MetodoPago,
    Pago,
    RecomendacionIA,
)
from alquiler.ui.logica import formato, inicio

MANANA = lambda: datetime(2026, 3, 10, 9, 0)  # noqa: E731


def _alquiler(s, codigo, fin, estado=EstadoAlquiler.ACTIVO, inicio_=date(2026, 3, 1)):
    cliente = s.query(Cliente).first()
    equipo = s.query(Equipo).filter_by(codigo=codigo).one()
    a = Alquiler(cliente=cliente, equipo=equipo, fecha_inicio=inicio_, fecha_fin_prevista=fin,
                 tarifa_diaria=10_000, costo_estimado=10_000 * ((fin - inicio_).days or 1),
                 estado=estado)
    s.add(a)
    return a


@pytest.fixture
def mas_equipos(fabrica, datos_base):
    with fabrica() as s:
        cat = s.query(Equipo).first().categoria
        for i in range(3, 6):
            s.add(Equipo(codigo=f"TAL-00{i}", nombre="Taladro", categoria=cat,
                         tarifa_diaria=20_000, fecha_adquisicion=date(2025, 1, 1)))
        s.commit()


def test_fecha_larga():
    assert inicio.fecha_larga(date(2026, 10, 4)) == "Domingo 4 de octubre de 2026"
    assert inicio.fecha_larga(date(2026, 3, 10)) == "Martes 10 de marzo de 2026"


def test_saludo_para():
    assert [inicio.saludo_para(h) for h in (4, 5, 11, 12, 18, 19)] == [
        "Buenas noches", "Buenos días", "Buenos días", "Buenas tardes", "Buenas tardes",
        "Buenas noches"]


def test_saludo_con_nombre(ctx_factory, datos_base):
    r = inicio.resumen(ctx_factory("admin"), ahora=MANANA)
    assert r["saludo"] == {"texto": "Buenos días, Admin", "fecha": "Martes 10 de marzo de 2026"}


def test_admin_ve_todos_los_bloques(ctx_factory, datos_base):
    assert set(inicio.resumen(ctx_factory("admin"), ahora=MANANA)) == {
        "saludo", "flota", "operacion", "mantenimiento", "ingresos_mes", "alerta_ia"}


def test_empleado_sin_ingresos(ctx_factory, datos_base):
    assert set(inicio.resumen(ctx_factory("empleado"), ahora=MANANA)) == {
        "saludo", "flota", "operacion", "mantenimiento", "alerta_ia"}


def test_cliente_solo_lo_suyo(ctx_factory, datos_base):
    assert set(inicio.resumen(ctx_factory("cliente"), ahora=MANANA)) == {"saludo", "mis_alquileres"}


def test_cliente_sin_cliente_vinculado(ctx_factory, datos_base, fabrica):
    from alquiler.ui.logica.contexto import Contexto, UsuarioSesion
    ctx = ctx_factory("cliente")
    sesion = UsuarioSesion(**{**ctx.usuario.__dict__, "cliente_id": None})
    huerfano = Contexto(fabrica, sesion, ctx.config, reloj=ctx.hoy)
    assert set(inicio.resumen(huerfano, ahora=MANANA)) == {"saludo"}


def test_conteos_operacion(ctx_factory, mas_equipos, fabrica):
    with fabrica() as s:
        _alquiler(s, "TAL-001", date(2026, 3, 9))    # vencido
        _alquiler(s, "TAL-002", date(2026, 3, 10))   # vence hoy
        _alquiler(s, "TAL-003", date(2026, 3, 15))   # al día
        _alquiler(s, "TAL-004", date(2026, 3, 20), EstadoAlquiler.RESERVADO, date(2026, 3, 12))
        _alquiler(s, "TAL-005", date(2026, 3, 2), EstadoAlquiler.FINALIZADO)
        s.commit()
    r = inicio.resumen(ctx_factory("empleado"), ahora=MANANA)
    assert r["operacion"] == {"activos": 3, "vencidos": 1, "vencen_hoy": 1,
                              "reservas_pendientes": 1}


def test_flota_por_estado(ctx_factory, mas_equipos, fabrica):
    with fabrica() as s:
        s.query(Equipo).filter_by(codigo="TAL-003").one().estado = EstadoEquipo.FUERA_DE_SERVICIO
        s.query(Equipo).filter_by(codigo="TAL-004").one().estado = EstadoEquipo.ALQUILADO
        s.commit()
    flota = inicio.resumen(ctx_factory("admin"), ahora=MANANA)["flota"]
    assert flota["conteos"] == [("Disponible", 3), ("Alquilado", 1), ("Reservado", 0),
                                ("En mantenimiento", 0), ("Fuera de servicio", 1)]
    assert (flota["total"], flota["disponibles"]) == (5, 3)


def test_ingresos_del_mes(ctx_factory, datos_base, fabrica):
    with fabrica() as s:
        a = _alquiler(s, "TAL-001", date(2026, 3, 15), inicio_=date(2026, 2, 25))
        s.add_all([Pago(alquiler=a, monto=50_000, fecha=date(2026, 3, 2),
                        metodo=MetodoPago.EFECTIVO, concepto=ConceptoPago.ALQUILER),
                   Pago(alquiler=a, monto=10_000, fecha=date(2026, 2, 27),
                        metodo=MetodoPago.EFECTIVO, concepto=ConceptoPago.ALQUILER)])
        s.commit()
    assert inicio.resumen(ctx_factory("admin"), ahora=MANANA)["ingresos_mes"] == {
        "valor": 50_000, "texto": "$50.000"}


def test_inicio_no_persiste_recomendaciones(ctx_factory, datos_base, fabrica):
    with fabrica() as s:  # muy por encima del intervalo de 20 usos: el recomendador lo marca
        s.query(Equipo).filter_by(codigo="TAL-001").one().usos_acumulados = 80
        s.commit()
    ctx = ctx_factory("admin")
    for _ in range(3):
        alerta = inicio.resumen(ctx, ahora=MANANA)["alerta_ia"]
    assert alerta["equipos"] >= 1 and alerta["confianza"]
    with fabrica() as s:
        assert s.query(RecomendacionIA).count() == 0


def test_alerta_ia_es_estimacion(ctx_factory, datos_base):
    alerta = inicio.resumen(ctx_factory("admin"), ahora=MANANA)["alerta_ia"]
    assert alerta["equipos"] == 0 and alerta["texto"].startswith("Estimación:")
    assert alerta["confianza"] in {"alta", "media", "baja", ""}


def test_texto_alerta_singular_y_plural():
    assert inicio.texto_alerta(1) == "Estimación: 1 equipo a revisar"
    assert inicio.texto_alerta(6) == "Estimación: 6 equipos a revisar"
    assert inicio.texto_alerta(0) == "Estimación: ningún equipo supera el umbral de revisión"


def test_confianza_predominante():
    assert inicio.confianza_predominante(["alta", "alta", "media"]) == "alta"
    assert inicio.confianza_predominante(["alta", "baja"]) == "baja"  # empate: la más prudente
    assert inicio.confianza_predominante([]) == ""


def test_base_vacia(ctx_factory):
    r = inicio.resumen(ctx_factory("admin"), ahora=MANANA)
    assert r["flota"]["total"] == 0 and r["flota"]["disponibles"] == 0
    assert r["operacion"] == {"activos": 0, "vencidos": 0, "vencen_hoy": 0,
                              "reservas_pendientes": 0}
    assert r["mantenimiento"] == {"abiertos": 0}
    assert inicio.tarjetas_kpi(r, {"equipos", "alquileres"})  # se construyen sin errores


def test_tarjetas_destino_solo_visible(ctx_factory, datos_base):
    r = inicio.resumen(ctx_factory("admin"), ahora=MANANA)
    tarjetas = {t["clave"]: t for t in inicio.tarjetas_kpi(r, {"equipos"})}
    assert tarjetas["disponibles"]["destino"] == "equipos"
    assert tarjetas["disponibles"]["valor"] == "2 / 2"
    assert tarjetas["activos"]["destino"] is None
    assert list(tarjetas) == ["disponibles", "activos", "vencidos", "vencen_hoy",
                              "reservas", "mantenimiento", "ingresos"]


@pytest.mark.parametrize("vencidos, tono", [(0, "neutro"), (2, "peligro")])
def test_tarjeta_vencidos_tono(vencidos, tono):
    r = {"operacion": {"activos": 5, "vencidos": vencidos, "vencen_hoy": 0,
                       "reservas_pendientes": 0}}
    [t] = [t for t in inicio.tarjetas_kpi(r, set()) if t["clave"] == "vencidos"]
    assert t["tono"] == tono and t["valor"] == str(vencidos)


def test_mis_alquileres(ctx_factory, datos_base, fabrica):
    with fabrica() as s:
        a = _alquiler(s, "TAL-001", date(2026, 3, 14))  # 13 días × 10.000 = 130.000
        _alquiler(s, "TAL-002", date(2026, 3, 12))
        s.add(Pago(alquiler=a, monto=30_000, fecha=date(2026, 3, 1),
                   metodo=MetodoPago.EFECTIVO, concepto=ConceptoPago.ALQUILER))
        s.commit()
    mios = inicio.resumen(ctx_factory("cliente"), ahora=MANANA)["mis_alquileres"]
    assert mios["activos"] == 2
    assert mios["proximo"] == formato.fecha(date(2026, 3, 12))
    assert mios["saldo"] == 100_000 + 110_000
    assert mios["saldo_texto"] == "$210.000"
    claves = [t["clave"] for t in inicio.tarjetas_kpi(
        inicio.resumen(ctx_factory("cliente"), ahora=MANANA), {"perfil"})]
    assert claves == ["mis_activos", "mi_saldo"]
