"""Lógica de presentación: alquileres, devoluciones, pagos y reservas."""

from datetime import date

from alquiler.auth import Permiso, requerir_permiso
from alquiler.models import Alquiler, ConceptoPago, EstadoAlquiler, MetodoPago
from alquiler.services import alquileres as svc
from alquiler.services import devoluciones as svc_dev
from alquiler.services import obtener
from alquiler.ui.logica import catalogo
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import fecha, pesos

ESTADOS_ALQUILER: list[tuple[str | None, str]] = [
    ("activo", "Activos"), ("finalizado", "Finalizados"), ("cancelado", "Cancelados"),
    (None, "Todos")]
METODOS: list[tuple[str, str]] = [(m.value, m.value.capitalize()) for m in MetodoPago]
CONCEPTOS: list[tuple[str, str]] = [("alquiler", "Alquiler"), ("mora", "Mora"),
                                    ("danos", "Daños")]


def _dias(n: int) -> str:
    return f"{n} día" if n == 1 else f"{n} días"


def equipos_disponibles(ctx: Contexto) -> list[dict]:
    return [{"id": e["id"], "tarifa_valor": e["tarifa_valor"],
             "etiqueta": f"{e['codigo']} · {e['nombre']} — {e['tarifa']}/día"}
            for e in catalogo.equipos(ctx, estado="Disponible")]


def cotizar(inicio: date, fin: date, tarifa: int) -> dict:
    if fin < inicio:
        return {"dias": None, "costo": None,
                "texto": "La devolución debe ser igual o posterior al inicio."}
    dias = svc.dias_contratados(inicio, fin)
    costo = svc.calcular_costo(inicio, fin, tarifa)
    return {"dias": dias, "costo": costo,
            "texto": f"{_dias(dias)} × {pesos(tarifa)} = {pesos(costo)}"}


def crear_alquiler(ctx: Contexto, cliente_id: int, equipo_id: int, inicio: date, fin: date) -> int:
    return ctx.ejecutar(lambda s, a: svc.crear_alquiler(
        s, a, cliente_id, equipo_id, inicio, fin, hoy=ctx.hoy()).id)


def _fila(alq, hoy: date) -> dict:
    saldo = svc.saldo_pendiente(alq)
    situacion = ""
    if alq.estado is EstadoAlquiler.ACTIVO:
        situacion = "vencido" if alq.fecha_fin_prevista < hoy else "al día"
    return {
        "id": alq.id, "cliente": alq.cliente.nombre,
        "equipo": f"{alq.equipo.codigo} · {alq.equipo.nombre}",
        "inicio": fecha(alq.fecha_inicio), "inicio__orden": alq.fecha_inicio.isoformat(),
        "inicio_valor": alq.fecha_inicio,
        "fin": fecha(alq.fecha_fin_prevista), "fin__orden": alq.fecha_fin_prevista.isoformat(),
        "estado": alq.estado.value, "situacion": situacion,
        "total": pesos(svc.total_adeudado(alq)), "saldo": pesos(saldo), "saldo__orden": saldo,
        "costo": pesos(alq.costo_estimado),
    }


def alquileres(ctx: Contexto, estado: str | None = "activo") -> list[dict]:
    hoy = ctx.hoy()
    filtro = EstadoAlquiler(estado) if estado else None
    return ctx.ejecutar(lambda s, a: [_fila(alq, hoy) for alq in svc.listar_alquileres(s, a, filtro)])


# ---------------------------------------------------------------- devolución y pagos
def previsualizar_devolucion(ctx: Contexto, alquiler_id: int, fecha_devolucion: date,
                             penalizacion: int = 0) -> dict:
    def calcular(s, a):
        requerir_permiso(a, Permiso.ALQUILERES_VER)
        alq = obtener(s, Alquiler, alquiler_id)
        return svc_dev.liquidar(alq, fecha_devolucion, ctx.config.factor_mora, penalizacion)

    liq = ctx.ejecutar(calcular)
    if liq.dias_retraso:
        texto = (f"{_dias(liq.dias_retraso)} de retraso → mora {pesos(liq.recargo_mora)}. "
                 f"Total a pagar: {pesos(liq.total)}")
    else:
        texto = f"Sin retraso. Total a pagar: {pesos(liq.total)}"
    return {"dias_retraso": liq.dias_retraso, "mora": liq.recargo_mora, "total": liq.total,
            "texto": texto}


def registrar_devolucion(ctx: Contexto, alquiler_id: int, fecha_devolucion: date, horas: float,
                         con_danos: bool, descripcion: str, penalizacion: int) -> None:
    ctx.ejecutar(lambda s, a: svc_dev.registrar_devolucion(
        s, a, alquiler_id, fecha_devolucion, horas, ctx.config.factor_mora,
        con_danos=con_danos, descripcion_danos=descripcion,
        penalizacion_danos=penalizacion if con_danos else 0))


def saldo(ctx: Contexto, alquiler_id: int) -> int:
    def calcular(s, a):
        requerir_permiso(a, Permiso.ALQUILERES_VER)
        return svc.saldo_pendiente(obtener(s, Alquiler, alquiler_id))
    return ctx.ejecutar(calcular)


def registrar_pago(ctx: Contexto, alquiler_id: int, monto: int, metodo: str, concepto: str) -> None:
    ctx.ejecutar(lambda s, a: svc.registrar_pago(
        s, a, alquiler_id, monto, MetodoPago(metodo), ConceptoPago(concepto), hoy=ctx.hoy()))


# ---------------------------------------------------------------- reservas
def _situacion_reserva(alq, hoy: date) -> str:
    if alq.fecha_fin_prevista < hoy:
        return "vencida"
    if alq.fecha_inicio <= hoy:
        return "lista para entregar"
    return "pendiente"


def reservas(ctx: Contexto) -> list[dict]:
    hoy = ctx.hoy()
    return ctx.ejecutar(lambda s, a: [
        {**_fila(alq, hoy), "situacion": _situacion_reserva(alq, hoy)}
        for alq in sorted(svc.listar_alquileres(s, a, EstadoAlquiler.RESERVADO),
                          key=lambda x: x.fecha_inicio)])


def entregar_reserva(ctx: Contexto, alquiler_id: int) -> None:
    ctx.ejecutar(lambda s, a: svc.entregar_reserva(s, a, alquiler_id, hoy=ctx.hoy()))


def cancelar_reserva(ctx: Contexto, alquiler_id: int) -> None:
    ctx.ejecutar(lambda s, a: svc.cancelar_alquiler(s, a, alquiler_id))
