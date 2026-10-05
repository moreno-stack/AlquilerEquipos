"""Lógica de presentación: catálogo de equipos, categorías y mantenimiento."""

from datetime import date

from alquiler.models import EstadoEquipo, TipoMantenimiento
from alquiler.services import equipos as svc_equipos
from alquiler.services import mantenimiento as svc_mant
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import fecha, pesos

ESTADOS: list[str] = [e.value for e in EstadoEquipo]
TIPOS_MANTENIMIENTO: list[str] = [t.value for t in TipoMantenimiento]


def categorias(ctx: Contexto) -> list[dict]:
    return ctx.ejecutar(lambda s, a: [{"id": c.id, "nombre": c.nombre}
                                      for c in svc_equipos.listar_categorias(s, a)])


def _fila(e) -> dict:
    return {
        "id": e.id, "codigo": e.codigo, "nombre": e.nombre, "categoria": e.categoria.nombre,
        "categoria_id": e.categoria_id, "estado": e.estado.value,
        "tarifa": pesos(e.tarifa_diaria), "tarifa__orden": e.tarifa_diaria,
        "tarifa_valor": e.tarifa_diaria, "usos": e.usos_acumulados,
        "usos__orden": e.usos_acumulados, "fecha_adquisicion": e.fecha_adquisicion,
        "descripcion": e.descripcion or "",
    }


def equipos(ctx: Contexto, texto: str | None = None, estado: str | None = None,
            categoria_id: int | None = None) -> list[dict]:
    filtro = EstadoEquipo(estado) if estado else None
    return ctx.ejecutar(lambda s, a: [
        _fila(e) for e in svc_equipos.listar_equipos(s, a, filtro, categoria_id, texto)])


def estados_posibles(estado: str) -> list[str]:
    alcanzables = svc_equipos.TRANSICIONES[EstadoEquipo(estado)]
    return [e for e in ESTADOS if EstadoEquipo(e) in alcanzables]


def crear_equipo(ctx: Contexto, codigo: str, nombre: str, categoria_id: int, tarifa: int,
                 fecha_adquisicion: date) -> int:
    return ctx.ejecutar(lambda s, a: svc_equipos.crear_equipo(
        s, a, codigo, nombre, categoria_id, tarifa, fecha_adquisicion).id)


def actualizar_equipo(ctx: Contexto, equipo_id: int, **campos) -> None:
    ctx.ejecutar(lambda s, a: svc_equipos.actualizar_equipo(s, a, equipo_id, **campos))


def dar_de_baja(ctx: Contexto, equipo_id: int) -> None:
    ctx.ejecutar(lambda s, a: svc_equipos.dar_de_baja(s, a, equipo_id))


def eliminar_equipo(ctx: Contexto, equipo_id: int) -> None:
    ctx.ejecutar(lambda s, a: svc_equipos.eliminar_equipo(s, a, equipo_id))


def crear_categoria(ctx: Contexto, nombre: str, usos: int = 20, dias: int = 90) -> int:
    return ctx.ejecutar(lambda s, a: svc_equipos.crear_categoria(s, a, nombre, None, usos, dias).id)


# ---------------------------------------------------------------- mantenimiento
def _etiqueta(equipo) -> str:
    return f"{equipo.codigo} · {equipo.nombre}"


def mantenimientos_abiertos(ctx: Contexto) -> list[dict]:
    hoy = ctx.hoy()
    return ctx.ejecutar(lambda s, a: [{
        "id": m.id, "equipo": _etiqueta(m.equipo), "tipo": m.tipo.value.capitalize(),
        "desde": fecha(m.fecha_inicio), "desde__orden": m.fecha_inicio.isoformat(),
        "dias": (hoy - m.fecha_inicio).days, "dias__orden": (hoy - m.fecha_inicio).days,
        "descripcion": m.descripcion,
    } for m in svc_mant.mantenimientos_abiertos(s, a)])


def historial_mantenimiento(ctx: Contexto, equipo_id: int) -> list[dict]:
    return ctx.ejecutar(lambda s, a: [{
        "id": m.id, "tipo": m.tipo.value.capitalize(), "inicio": fecha(m.fecha_inicio),
        "fin": fecha(m.fecha_fin) or "En curso", "costo": pesos(m.costo),
        "costo__orden": m.costo, "descripcion": m.descripcion.replace("\n", " "),
    } for m in svc_mant.historial_mantenimiento(s, a, equipo_id)])


def equipos_para_mantenimiento(ctx: Contexto) -> list[dict]:
    return [{"id": e["id"], "etiqueta": f"{e['codigo']} · {e['nombre']}"} for e in equipos(ctx)]


def abrir_mantenimiento(ctx: Contexto, equipo_id: int, tipo: str, descripcion: str) -> int:
    return ctx.ejecutar(lambda s, a: svc_mant.abrir_mantenimiento(
        s, a, equipo_id, TipoMantenimiento(tipo), descripcion, hoy=ctx.hoy()).id)


def cerrar_mantenimiento(ctx: Contexto, mantenimiento_id: int, costo: int, notas: str) -> None:
    ctx.ejecutar(lambda s, a: svc_mant.cerrar_mantenimiento(
        s, a, mantenimiento_id, costo, notas, hoy=ctx.hoy()))
