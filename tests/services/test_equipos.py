"""Servicio de equipos: CRUD, catálogo por rol y máquina de estados (spec §4.3)."""

from datetime import date

import pytest

from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import Equipo, EstadoEquipo, Mantenimiento, TipoMantenimiento
from alquiler.services import equipos as svc

E = EstadoEquipo
VALIDAS = [
    (E.DISPONIBLE, E.ALQUILADO), (E.DISPONIBLE, E.RESERVADO),
    (E.DISPONIBLE, E.EN_MANTENIMIENTO), (E.DISPONIBLE, E.FUERA_DE_SERVICIO),
    (E.RESERVADO, E.DISPONIBLE), (E.RESERVADO, E.ALQUILADO),
    (E.ALQUILADO, E.DISPONIBLE), (E.ALQUILADO, E.EN_MANTENIMIENTO),
    (E.EN_MANTENIMIENTO, E.DISPONIBLE), (E.EN_MANTENIMIENTO, E.FUERA_DE_SERVICIO),
    (E.FUERA_DE_SERVICIO, E.EN_MANTENIMIENTO),
]
INVALIDAS = [
    (a, b) for a in E for b in E if a is not b and (a, b) not in VALIDAS
]


def test_la_tabla_cubre_11_validas_y_9_invalidas():
    assert len(VALIDAS) == 11 and len(INVALIDAS) == 9


@pytest.mark.parametrize("desde,hacia", VALIDAS)
def test_transiciones_validas(desde, hacia):
    equipo = Equipo(estado=desde)
    svc.transicionar(equipo, hacia)
    assert equipo.estado is hacia


@pytest.mark.parametrize("desde,hacia", INVALIDAS)
def test_transiciones_invalidas(desde, hacia):
    equipo = Equipo(estado=desde)
    with pytest.raises(ReglaNegocioError, match="Transición no permitida"):
        svc.transicionar(equipo, hacia)
    assert equipo.estado is desde


def _nuevo(session, actor, categoria, codigo="TAL-002", **kw):
    datos = dict(codigo=codigo, nombre="Taladro inalámbrico", categoria_id=categoria.id,
                 tarifa_diaria=30_000, fecha_adquisicion=date(2025, 6, 1))
    datos.update(kw)
    return svc.crear_equipo(session, actor, **datos)


def test_crear_equipo_normaliza_codigo(session, empleado, categoria):
    equipo = _nuevo(session, empleado, categoria, codigo=" tal-002 ")
    assert equipo.codigo == "TAL-002"
    assert equipo.estado is EstadoEquipo.DISPONIBLE


def test_codigo_duplicado_con_espacios_y_minusculas(session, empleado, categoria, equipo):
    with pytest.raises(ReglaNegocioError, match="TAL-001"):
        _nuevo(session, empleado, categoria, codigo=" tal-001 ")


@pytest.mark.parametrize("tarifa", [0, -1])
def test_tarifa_no_positiva_rechazada(session, empleado, categoria, tarifa):
    with pytest.raises(ReglaNegocioError):
        _nuevo(session, empleado, categoria, tarifa_diaria=tarifa)


def test_categoria_inexistente_rechazada(session, empleado, categoria):
    with pytest.raises(ReglaNegocioError, match="Categoría no existe"):
        _nuevo(session, empleado, categoria, categoria_id=999)


def test_crear_categoria_y_duplicada_sin_importar_mayusculas(session, empleado):
    categoria = svc.crear_categoria(session, empleado, " Andamios ", intervalo_mant_usos=10)
    assert (categoria.nombre, categoria.intervalo_mant_usos) == ("Andamios", 10)
    with pytest.raises(ReglaNegocioError):
        svc.crear_categoria(session, empleado, "ANDAMIOS")


def test_categoria_con_intervalo_no_positivo_rechazada(session, empleado):
    with pytest.raises(ReglaNegocioError):
        svc.crear_categoria(session, empleado, "Andamios", intervalo_mant_dias=0)


def test_actualizar_equipo_campo_no_permitido(session, empleado, equipo):
    with pytest.raises(ReglaNegocioError, match="estado"):
        svc.actualizar_equipo(session, empleado, equipo.id, estado=EstadoEquipo.ALQUILADO)
    assert equipo.estado is EstadoEquipo.DISPONIBLE


def test_actualizar_tarifa(session, empleado, equipo):
    svc.actualizar_equipo(session, empleado, equipo.id, tarifa_diaria=27_000, nombre="Taladro X")
    assert (equipo.tarifa_diaria, equipo.nombre) == (27_000, "Taladro X")


def test_actualizar_con_tarifa_invalida_no_deja_cambios(session, empleado, equipo):
    with pytest.raises(ReglaNegocioError):
        svc.actualizar_equipo(session, empleado, equipo.id, nombre="Nuevo", tarifa_diaria=0)
    # Sin refresh: el objeto en memoria tampoco debe quedar modificado a medias.
    assert (equipo.nombre, equipo.tarifa_diaria) == ("Taladro percutor", 25_000)


def test_dar_de_baja_equipo_alquilado_rechazado(session, empleado, equipo):
    equipo.estado = EstadoEquipo.ALQUILADO
    session.commit()
    with pytest.raises(ReglaNegocioError, match="Transición no permitida"):
        svc.dar_de_baja(session, empleado, equipo.id)


def test_dar_de_baja_disponible(session, empleado, equipo):
    assert svc.dar_de_baja(session, empleado, equipo.id).estado is EstadoEquipo.FUERA_DE_SERVICIO


def test_eliminar_equipo_con_historial_rechazado(session, admin, equipo):
    session.add(Mantenimiento(equipo=equipo, tipo=TipoMantenimiento.PREVENTIVO,
                              fecha_inicio=date(2026, 1, 1), descripcion="Revisión"))
    session.commit()
    with pytest.raises(ReglaNegocioError, match="historial"):
        svc.eliminar_equipo(session, admin, equipo.id)


def test_eliminar_equipo_sin_historial(session, admin, equipo):
    svc.eliminar_equipo(session, admin, equipo.id)
    assert session.get(Equipo, equipo.id) is None


def test_empleado_no_puede_eliminar(session, empleado, equipo):
    with pytest.raises(PermisoDenegado):
        svc.eliminar_equipo(session, empleado, equipo.id)


def test_cliente_no_puede_crear(session, usuario_cliente, categoria):
    with pytest.raises(PermisoDenegado):
        _nuevo(session, usuario_cliente, categoria)


def test_cliente_solo_ve_disponibles(session, empleado, usuario_cliente, categoria, equipo):
    _nuevo(session, empleado, categoria).estado = EstadoEquipo.EN_MANTENIMIENTO
    session.commit()
    assert [e.codigo for e in svc.listar_equipos(session, usuario_cliente)] == ["TAL-001"]
    assert len(svc.listar_equipos(session, empleado)) == 2


def test_cliente_no_ve_no_disponibles_aunque_los_filtre(session, usuario_cliente, equipo):
    equipo.estado = EstadoEquipo.ALQUILADO
    session.commit()
    assert svc.listar_equipos(session, usuario_cliente, estado=EstadoEquipo.ALQUILADO) == []


def test_listar_filtra_por_texto_estado_y_categoria(session, empleado, categoria, equipo):
    otra = svc.crear_categoria(session, empleado, "Andamios")
    _nuevo(session, empleado, otra, codigo="AND-001", nombre="Andamio tubular")
    assert [e.codigo for e in svc.listar_equipos(session, empleado, texto="andamio")] == ["AND-001"]
    assert [e.codigo for e in svc.listar_equipos(session, empleado, texto="tal-")] == ["TAL-001"]
    assert [e.codigo for e in svc.listar_equipos(session, empleado, categoria_id=otra.id)] == ["AND-001"]
    assert svc.listar_equipos(session, empleado, estado=EstadoEquipo.ALQUILADO) == []
    assert [e.codigo for e in svc.listar_equipos(session, empleado)] == ["AND-001", "TAL-001"]


def test_listar_categorias(session, usuario_cliente, categoria):
    assert [c.nombre for c in svc.listar_categorias(session, usuario_cliente)] == ["Taladros"]
