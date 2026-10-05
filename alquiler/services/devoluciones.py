"""Devoluciones: retraso, mora, daños y actualización del equipo (spec §4.4)."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from alquiler.auth import Permiso, requerir_permiso
from alquiler.errors import ReglaNegocioError
from alquiler.models import Alquiler, Devolucion, EstadoAlquiler, EstadoEquipo, TipoMantenimiento, Usuario
from alquiler.services import obtener
from alquiler.services.equipos import transicionar
from alquiler.services.mantenimiento import abrir


@dataclass(frozen=True)
class Liquidacion:
    dias_retraso: int
    recargo_mora: int
    total: int


def liquidar(
    alquiler: Alquiler, fecha_devolucion: date, factor_mora: float, penalizacion_danos: int = 0
) -> Liquidacion:
    dias_retraso = max(0, (fecha_devolucion - alquiler.fecha_fin_prevista).days)
    # Decimal(str()) evita el error binario de float; ROUND_HALF_UP evita el redondeo bancario.
    mora = Decimal(dias_retraso * alquiler.tarifa_diaria) * Decimal(str(factor_mora))
    recargo_mora = int(mora.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    total = alquiler.costo_estimado + recargo_mora + penalizacion_danos
    return Liquidacion(dias_retraso, recargo_mora, total)


def registrar_devolucion(
    session: Session,
    actor: Usuario,
    alquiler_id: int,
    fecha_devolucion: date,
    horas_uso: float,
    factor_mora: float,
    con_danos: bool = False,
    descripcion_danos: str | None = None,
    penalizacion_danos: int = 0,
) -> Devolucion:
    requerir_permiso(actor, Permiso.DEVOLUCIONES_REGISTRAR)
    alquiler = obtener(session, Alquiler, alquiler_id)
    descripcion_danos = (descripcion_danos or "").strip() or None

    if alquiler.estado is not EstadoAlquiler.ACTIVO:
        raise ReglaNegocioError(
            f"El alquiler no está activo (estado: {alquiler.estado.value}); no se puede devolver."
        )
    if fecha_devolucion < alquiler.fecha_inicio:
        raise ReglaNegocioError("La fecha de devolución no puede ser anterior al inicio del alquiler.")
    if horas_uso < 0:
        raise ReglaNegocioError("Las horas de uso no pueden ser negativas.")
    if penalizacion_danos < 0:
        raise ReglaNegocioError("La penalización por daños no puede ser negativa.")
    if con_danos and descripcion_danos is None:
        raise ReglaNegocioError("Si hay daños, debe describirlos.")
    if not con_danos and penalizacion_danos > 0:
        raise ReglaNegocioError("Solo se cobra penalización cuando se registran daños.")

    liquidacion = liquidar(alquiler, fecha_devolucion, factor_mora, penalizacion_danos)
    equipo = alquiler.equipo
    equipo.usos_acumulados += 1
    equipo.horas_uso_acumuladas += horas_uso
    if con_danos:
        abrir(session, equipo, TipoMantenimiento.CORRECTIVO,
              f"Daños reportados en devolución: {descripcion_danos}", fecha_devolucion)
    else:
        transicionar(equipo, EstadoEquipo.DISPONIBLE)
    alquiler.estado = EstadoAlquiler.FINALIZADO

    devolucion = Devolucion(
        alquiler=alquiler,
        fecha_devolucion=fecha_devolucion,
        dias_retraso=liquidacion.dias_retraso,
        recargo_mora=liquidacion.recargo_mora,
        horas_uso=horas_uso,
        con_danos=con_danos,
        descripcion_danos=descripcion_danos,
        penalizacion_danos=penalizacion_danos,
        total=liquidacion.total,
        registrado_por_id=actor.id,
    )
    session.add(devolucion)
    session.commit()
    return devolucion
