"""Reportes: ingresos, uso de flota y morosidad (spec §7)."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler.auth import Permiso, requerir_permiso
from alquiler.errors import ReglaNegocioError
from alquiler.models import (
    Alquiler,
    ConceptoPago,
    Devolucion,
    Equipo,
    EstadoAlquiler,
    Pago,
    Usuario,
)
from alquiler.services.devoluciones import liquidar

UN_DIA = timedelta(days=1)


@dataclass
class Ingresos:
    total: int
    por_concepto: dict[ConceptoPago, int]
    por_mes: dict[str, int]


@dataclass
class UsoEquipo:
    equipo_id: int
    codigo: str
    nombre: str
    categoria: str
    dias_alquilado: int
    dias_periodo: int
    porcentaje: float


@dataclass
class AlquilerVencido:
    alquiler_id: int
    cliente: str
    equipo: str
    dias_vencido: int
    mora_estimada: int


@dataclass
class Morosidad:
    vencidos: list[AlquilerVencido]
    mora_facturada: int
    mora_cobrada: int
    tasa_retraso: float


def _validar_periodo(desde: date, hasta: date) -> None:
    if desde > hasta:
        raise ReglaNegocioError("El período no es válido: la fecha inicial es posterior a la final.")


def ingresos(session: Session, actor: Usuario, desde: date, hasta: date) -> Ingresos:
    requerir_permiso(actor, Permiso.REPORTES_VER)
    _validar_periodo(desde, hasta)
    pagos = session.scalars(select(Pago).where(Pago.fecha.between(desde, hasta)))
    por_concepto = {c: 0 for c in ConceptoPago}
    por_mes: dict[str, int] = defaultdict(int)
    for pago in pagos:
        por_concepto[pago.concepto] += pago.monto
        por_mes[pago.fecha.strftime("%Y-%m")] += pago.monto
    return Ingresos(sum(por_concepto.values()), por_concepto, dict(sorted(por_mes.items())))


def _dias_ocupados(alquiler: Alquiler, desde: date, hasta: date, hoy: date) -> int:
    """Días del período en que el equipo estuvo fuera, con intervalo [inicio, fin)."""
    if alquiler.devolucion is not None:
        fin = max(alquiler.devolucion.fecha_devolucion, alquiler.fecha_inicio + UN_DIA)
    else:  # activo: cuenta hasta hoy inclusive
        fin = min(hoy, hasta) + UN_DIA
    inicio = max(alquiler.fecha_inicio, desde)
    fin = min(fin, hasta + UN_DIA)
    return max(0, (fin - inicio).days)


def uso_flota(
    session: Session, actor: Usuario, desde: date, hasta: date, hoy: date | None = None
) -> list[UsoEquipo]:
    requerir_permiso(actor, Permiso.REPORTES_VER)
    _validar_periodo(desde, hasta)
    hoy = hoy or date.today()
    dias_periodo = (hasta - desde).days + 1
    contados = (EstadoAlquiler.ACTIVO, EstadoAlquiler.FINALIZADO)
    usos = []
    for equipo in session.scalars(select(Equipo)):
        dias = sum(
            _dias_ocupados(a, desde, hasta, hoy) for a in equipo.alquileres if a.estado in contados
        )
        usos.append(UsoEquipo(
            equipo_id=equipo.id,
            codigo=equipo.codigo,
            nombre=equipo.nombre,
            categoria=equipo.categoria.nombre,
            dias_alquilado=dias,
            dias_periodo=dias_periodo,
            porcentaje=round(100 * dias / dias_periodo, 1),
        ))
    return sorted(usos, key=lambda u: (-u.porcentaje, u.codigo))


def uso_por_categoria(
    session: Session, actor: Usuario, desde: date, hasta: date, hoy: date | None = None
) -> dict[str, float]:
    dias: dict[str, int] = defaultdict(int)
    equipos: dict[str, int] = defaultdict(int)
    for uso in uso_flota(session, actor, desde, hasta, hoy):
        dias[uso.categoria] += uso.dias_alquilado
        equipos[uso.categoria] += 1
    dias_periodo = (hasta - desde).days + 1
    return {c: round(100 * dias[c] / (equipos[c] * dias_periodo), 1) for c in sorted(dias)}


def morosidad(
    session: Session, actor: Usuario, factor_mora: float, hoy: date | None = None
) -> Morosidad:
    requerir_permiso(actor, Permiso.REPORTES_VER)
    hoy = hoy or date.today()
    vencidos = [
        AlquilerVencido(
            alquiler_id=a.id,
            cliente=a.cliente.nombre,
            equipo=a.equipo.codigo,
            dias_vencido=(hoy - a.fecha_fin_prevista).days,
            mora_estimada=liquidar(a, hoy, factor_mora).recargo_mora,
        )
        for a in session.scalars(
            select(Alquiler)
            .where(Alquiler.estado == EstadoAlquiler.ACTIVO, Alquiler.fecha_fin_prevista < hoy)
            .order_by(Alquiler.fecha_fin_prevista)
        )
    ]
    devoluciones = list(session.scalars(select(Devolucion)))
    con_retraso = sum(1 for d in devoluciones if d.dias_retraso > 0)
    mora_cobrada = sum(session.scalars(
        select(Pago.monto).where(Pago.concepto == ConceptoPago.MORA)
    ))
    return Morosidad(
        vencidos=vencidos,
        mora_facturada=sum(d.recargo_mora for d in devoluciones),
        mora_cobrada=mora_cobrada,
        tasa_retraso=con_retraso / len(devoluciones) if devoluciones else 0.0,
    )
