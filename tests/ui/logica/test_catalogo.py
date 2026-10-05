"""Lógica de presentación del catálogo de equipos y del mantenimiento."""

from datetime import date

import pytest

from alquiler.errors import ReglaNegocioError
from alquiler.ui.logica import catalogo


def test_equipos_filtrados_y_formateados(ctx_factory, datos_base):
    ctx = ctx_factory("admin")
    filas = catalogo.equipos(ctx)
    assert [f["codigo"] for f in filas] == ["TAL-001", "TAL-002"]
    f = filas[0]
    assert (f["tarifa"], f["tarifa__orden"], f["estado"], f["categoria"]) == (
        "$25.000", 25_000, "Disponible", "Taladros")
    assert [f["codigo"] for f in catalogo.equipos(ctx, texto="inalámb")] == ["TAL-002"]
    assert catalogo.equipos(ctx, estado="Alquilado") == []
    cat = catalogo.categorias(ctx)[0]
    assert len(catalogo.equipos(ctx, categoria_id=cat["id"])) == 2


def test_estados_posibles_refleja_la_tabla():
    assert catalogo.estados_posibles("Disponible") == [
        "Alquilado", "En mantenimiento", "Reservado", "Fuera de servicio"]
    assert catalogo.estados_posibles("Fuera de servicio") == ["En mantenimiento"]
    assert catalogo.ESTADOS[0] == "Disponible" and len(catalogo.ESTADOS) == 5


def test_crear_equipo_y_duplicado_no_escribe(ctx_factory, datos_base):
    ctx = ctx_factory("empleado")
    cat = catalogo.categorias(ctx)[0]["id"]
    nuevo = catalogo.crear_equipo(ctx, "tal-003", "Rotomartillo", cat, 35_000, date(2025, 5, 1))
    assert isinstance(nuevo, int)
    with pytest.raises(ReglaNegocioError, match="TAL-001"):
        catalogo.crear_equipo(ctx, "TAL-001", "Copia", cat, 1_000, date(2025, 5, 1))
    assert len(catalogo.equipos(ctx)) == 3


def test_cliente_solo_ve_disponibles(ctx_factory, datos_base):
    admin = ctx_factory("admin")
    catalogo.dar_de_baja(admin, catalogo.equipos(admin)[0]["id"])
    assert [f["codigo"] for f in catalogo.equipos(ctx_factory("cliente"))] == ["TAL-002"]


def test_mantenimiento_abrir_cerrar_e_historial(ctx_factory, datos_base):
    ctx = ctx_factory("empleado")
    equipo_id = catalogo.equipos(ctx)[0]["id"]
    m_id = catalogo.abrir_mantenimiento(ctx, equipo_id, "correctivo", "Cambio de mandril")
    [abierto] = catalogo.mantenimientos_abiertos(ctx)
    assert (abierto["id"], abierto["equipo"], abierto["tipo"], abierto["desde"]) == (
        m_id, "TAL-001 · Taladro percutor", "Correctivo", "10/03/2026")
    assert catalogo.equipos(ctx)[0]["estado"] == "En mantenimiento"
    catalogo.cerrar_mantenimiento(ctx, m_id, 45_000, "Mandril nuevo")
    assert catalogo.mantenimientos_abiertos(ctx) == []
    [h] = catalogo.historial_mantenimiento(ctx, equipo_id)
    assert (h["costo"], h["fin"]) == ("$45.000", "10/03/2026") and "Mandril nuevo" in h["descripcion"]


def test_crear_categoria(ctx_factory):
    ctx = ctx_factory("admin")
    catalogo.crear_categoria(ctx, "Andamios", 15, 120)
    assert [c["nombre"] for c in catalogo.categorias(ctx)] == ["Andamios"]
