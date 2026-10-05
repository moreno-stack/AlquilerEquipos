"""Contexto de la interfaz: sesión por operación, rollback y navegación por rol."""

from datetime import date

import pytest
from sqlalchemy import func, select

from alquiler.auth import crear_usuario
from alquiler.errors import CredencialesInvalidas, PermisoDenegado
from alquiler.models import Categoria, Rol, Usuario
from alquiler.ui.logica import formato
from alquiler.ui.logica.contexto import iniciar_sesion
from alquiler.ui.logica.navegacion import SECCIONES, secciones_para


def test_iniciar_sesion_ok_y_permisos_del_rol(fabrica, config):
    with fabrica() as s:
        crear_usuario(s, "luis", "clave-segura", Rol.EMPLEADO, "Luis Gómez")
    ctx = iniciar_sesion(fabrica, config, " LUIS ", "clave-segura")
    assert (ctx.usuario.username, ctx.usuario.rol, ctx.usuario.nombre) == (
        "luis", "empleado", "Luis Gómez")
    assert ctx.puede("alquileres.gestionar") and not ctx.puede("reportes.ver")
    assert isinstance(ctx.hoy(), date)


def test_credenciales_invalidas(fabrica, config):
    with pytest.raises(CredencialesInvalidas):
        iniciar_sesion(fabrica, config, "nadie", "x")


def test_ejecutar_hace_rollback_si_falla(ctx_factory, fabrica):
    ctx = ctx_factory("admin")

    def falla_a_medias(s, actor):
        s.add(Categoria(nombre="Fantasma"))
        s.flush()  # ya está en la transacción…
        raise RuntimeError("fallo después de escribir")

    with pytest.raises(RuntimeError):
        ctx.ejecutar(falla_a_medias)
    with fabrica() as s:
        assert s.scalar(select(func.count()).select_from(Categoria)) == 0


def test_tras_un_error_la_siguiente_operacion_funciona(ctx_factory, fabrica):
    ctx = ctx_factory("admin")
    with pytest.raises(ZeroDivisionError):
        ctx.ejecutar(lambda s, a: 1 / 0)
    ctx.ejecutar(lambda s, a: (s.add(Categoria(nombre="Real")), s.commit()))
    with fabrica() as s:
        assert s.scalar(select(Categoria.nombre)) == "Real"


def test_resultado_utilizable_tras_cerrar_sesion(ctx_factory):
    ctx = ctx_factory("admin")
    filas = ctx.ejecutar(lambda s, actor: [{"usuario": actor.username, "rol": actor.rol.value}])
    assert filas == [{"usuario": "admin", "rol": "administrador"}]


def test_ejecutar_recibe_al_actor_actual(ctx_factory):
    ctx = ctx_factory("empleado")
    assert ctx.ejecutar(lambda s, actor: actor.id) == ctx.usuario.id


def test_usuario_desactivado_durante_la_sesion(ctx_factory, fabrica):
    ctx = ctx_factory("empleado")
    with fabrica() as s:
        s.get(Usuario, ctx.usuario.id).activo = False
        s.commit()
    with pytest.raises(PermisoDenegado, match="sesión ya no es válida"):
        ctx.ejecutar(lambda s, a: None)


@pytest.mark.parametrize("rol,claves", [
    ("admin", [s.clave for s in SECCIONES]),
    ("empleado", ["inicio", "equipos", "mantenimiento", "clientes", "alquileres", "reservas",
                  "analisis_ia", "perfil"]),
    ("cliente", ["inicio", "equipos", "perfil"]),
])
def test_secciones_por_rol(ctx_factory, rol, claves):
    assert [s.clave for s in secciones_para(ctx_factory(rol))] == claves


def test_hay_11_secciones_con_inicio_primero():
    assert len(SECCIONES) == 11 and SECCIONES[0].clave == "inicio"


def test_formato_pesos_fecha_nivel():
    assert formato.pesos(1234567) == "$1.234.567"
    assert formato.fecha(date(2026, 3, 9)) == "09/03/2026"
    assert formato.fecha(None) == ""
    assert formato.nivel("alta") == "Alta"
