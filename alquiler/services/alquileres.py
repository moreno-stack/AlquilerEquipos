"""Alquileres: contratos, reservas, cancelaciones y pagos (spec §4.4)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler.auth import Permiso, requerir_permiso
from alquiler.errors import ReglaNegocioError
from alquiler.models import (
    Alquiler,
    Cliente,
    ConceptoPago,
    Equipo,
    EstadoAlquiler,
    EstadoEquipo,
    MetodoPago,
    Pago,
    Usuario,
)
from alquiler.services import obtener, pesos
from alquiler.services.equipos import transicionar


# ---------------------------------------------------------------- cálculos puros
def dias_contratados(inicio: date, fin: date) -> int:
    return max(1, (fin - inicio).days)


def calcular_costo(inicio: date, fin: date, tarifa_diaria: int) -> int:
    return dias_contratados(inicio, fin) * tarifa_diaria


def total_adeudado(alquiler: Alquiler) -> int:
    if alquiler.devolucion is not None:
        return alquiler.devolucion.total
    return alquiler.costo_estimado


def saldo_pendiente(alquiler: Alquiler) -> int:
    return total_adeudado(alquiler) - sum(p.monto for p in alquiler.pagos)


# ---------------------------------------------------------------- operaciones
def crear_alquiler(
    session: Session,
    actor: Usuario,
    cliente_id: int,
    equipo_id: int,
    fecha_inicio: date,
    fecha_fin_prevista: date,
    hoy: date | None = None,
) -> Alquiler:
    requerir_permiso(actor, Permiso.ALQUILERES_GESTIONAR)
    hoy = hoy or date.today()
    cliente = obtener(session, Cliente, cliente_id)
    equipo = obtener(session, Equipo, equipo_id)
    if not cliente.activo:
        raise ReglaNegocioError("El cliente está inactivo; no se le pueden registrar alquileres.")
    if fecha_inicio < hoy:
        raise ReglaNegocioError("La fecha de inicio no puede ser una fecha pasada.")
    if fecha_fin_prevista < fecha_inicio:
        raise ReglaNegocioError("La fecha de devolución prevista debe ser igual o posterior al inicio.")
    if equipo.estado is not EstadoEquipo.DISPONIBLE:
        raise ReglaNegocioError(
            f"El equipo {equipo.codigo} no está disponible (estado: {equipo.estado.value})."
        )

    reserva = fecha_inicio > hoy
    transicionar(equipo, EstadoEquipo.RESERVADO if reserva else EstadoEquipo.ALQUILADO)
    alquiler = Alquiler(
        cliente=cliente,
        equipo=equipo,
        registrado_por=actor,
        fecha_inicio=fecha_inicio,
        fecha_fin_prevista=fecha_fin_prevista,
        tarifa_diaria=equipo.tarifa_diaria,
        costo_estimado=calcular_costo(fecha_inicio, fecha_fin_prevista, equipo.tarifa_diaria),
        estado=EstadoAlquiler.RESERVADO if reserva else EstadoAlquiler.ACTIVO,
    )
    session.add(alquiler)
    session.commit()
    return alquiler


def _reserva(session: Session, alquiler_id: int) -> Alquiler:
    alquiler = obtener(session, Alquiler, alquiler_id)
    if alquiler.estado is not EstadoAlquiler.RESERVADO:
        raise ReglaNegocioError(
            f"Solo se puede operar sobre un alquiler reservado (estado: {alquiler.estado.value})."
        )
    return alquiler


def entregar_reserva(
    session: Session, actor: Usuario, alquiler_id: int, hoy: date | None = None
) -> Alquiler:
    requerir_permiso(actor, Permiso.ALQUILERES_GESTIONAR)
    hoy = hoy or date.today()
    alquiler = _reserva(session, alquiler_id)
    if hoy < alquiler.fecha_inicio:
        raise ReglaNegocioError(
            f"La reserva inicia el {alquiler.fecha_inicio.isoformat()}; aún no se puede entregar."
        )
    if hoy > alquiler.fecha_fin_prevista:
        raise ReglaNegocioError(
            "La reserva venció sin entregarse; cancélela y registre un alquiler nuevo."
        )
    transicionar(alquiler.equipo, EstadoEquipo.ALQUILADO)
    alquiler.estado = EstadoAlquiler.ACTIVO
    session.commit()
    return alquiler


def cancelar_alquiler(session: Session, actor: Usuario, alquiler_id: int) -> Alquiler:
    requerir_permiso(actor, Permiso.ALQUILERES_GESTIONAR)
    alquiler = _reserva(session, alquiler_id)
    transicionar(alquiler.equipo, EstadoEquipo.DISPONIBLE)
    alquiler.estado = EstadoAlquiler.CANCELADO
    session.commit()
    return alquiler


def registrar_pago(
    session: Session,
    actor: Usuario,
    alquiler_id: int,
    monto: int,
    metodo: MetodoPago,
    concepto: ConceptoPago,
    hoy: date | None = None,
) -> Pago:
    requerir_permiso(actor, Permiso.ALQUILERES_GESTIONAR)
    alquiler = obtener(session, Alquiler, alquiler_id)
    if alquiler.estado is EstadoAlquiler.CANCELADO:
        raise ReglaNegocioError("No se registran pagos a un alquiler cancelado.")
    if monto <= 0:
        raise ReglaNegocioError("El monto del pago debe ser mayor que 0.")
    saldo = saldo_pendiente(alquiler)
    if monto > saldo:
        raise ReglaNegocioError(f"El pago excede el saldo pendiente ({pesos(saldo)}).")
    pago = Pago(alquiler=alquiler, monto=monto, fecha=hoy or date.today(),
                metodo=metodo, concepto=concepto)
    session.add(pago)
    session.commit()
    return pago


# ---------------------------------------------------------------- consultas
def listar_alquileres(
    session: Session,
    actor: Usuario,
    estado: EstadoAlquiler | None = None,
    cliente_id: int | None = None,
) -> list[Alquiler]:
    requerir_permiso(actor, Permiso.ALQUILERES_VER)
    consulta = select(Alquiler).order_by(Alquiler.fecha_inicio.desc(), Alquiler.id.desc())
    if estado is not None:
        consulta = consulta.where(Alquiler.estado == estado)
    if cliente_id is not None:
        consulta = consulta.where(Alquiler.cliente_id == cliente_id)
    return list(session.scalars(consulta))


def alquileres_vencidos(session: Session, actor: Usuario, hoy: date | None = None) -> list[Alquiler]:
    requerir_permiso(actor, Permiso.ALQUILERES_VER)
    hoy = hoy or date.today()
    return list(session.scalars(
        select(Alquiler)
        .where(Alquiler.estado == EstadoAlquiler.ACTIVO, Alquiler.fecha_fin_prevista < hoy)
        .order_by(Alquiler.fecha_fin_prevista)
    ))
