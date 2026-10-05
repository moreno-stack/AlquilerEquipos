"""Mantenimiento preventivo y correctivo de equipos."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler.auth import Permiso, requerir_permiso
from alquiler.errors import ReglaNegocioError
from alquiler.models import Equipo, EstadoEquipo, Mantenimiento, TipoMantenimiento, Usuario
from alquiler.services import obtener
from alquiler.services.equipos import transicionar


def abrir(
    session: Session, equipo: Equipo, tipo: TipoMantenimiento, descripcion: str, fecha: date
) -> Mantenimiento:
    """Abre un mantenimiento sin verificar permisos ni hacer commit.

    Lo usan ``abrir_mantenimiento`` y el registro de devoluciones con daños.
    """
    descripcion = descripcion.strip()
    if not descripcion:
        raise ReglaNegocioError("La descripción del mantenimiento es obligatoria.")
    if equipo.estado is EstadoEquipo.EN_MANTENIMIENTO:
        raise ReglaNegocioError(f"El equipo {equipo.codigo} ya tiene un mantenimiento abierto.")
    transicionar(equipo, EstadoEquipo.EN_MANTENIMIENTO)
    mantenimiento = Mantenimiento(
        equipo=equipo,
        tipo=tipo,
        fecha_inicio=fecha,
        descripcion=descripcion,
        usos_al_momento=equipo.usos_acumulados,
    )
    session.add(mantenimiento)
    return mantenimiento


def abrir_mantenimiento(
    session: Session,
    actor: Usuario,
    equipo_id: int,
    tipo: TipoMantenimiento,
    descripcion: str,
    hoy: date | None = None,
) -> Mantenimiento:
    requerir_permiso(actor, Permiso.MANTENIMIENTO_GESTIONAR)
    equipo = obtener(session, Equipo, equipo_id)
    # Alquilado → En mantenimiento solo ocurre al devolver con daños, nunca a mano.
    if equipo.estado in (EstadoEquipo.ALQUILADO, EstadoEquipo.RESERVADO):
        raise ReglaNegocioError(
            f"El equipo {equipo.codigo} está {equipo.estado.value.lower()}; "
            "solo se abre mantenimiento a equipos disponibles o fuera de servicio."
        )
    mantenimiento = abrir(session, equipo, tipo, descripcion, hoy or date.today())
    session.commit()
    return mantenimiento


def cerrar_mantenimiento(
    session: Session,
    actor: Usuario,
    mantenimiento_id: int,
    costo: int = 0,
    notas: str | None = None,
    hoy: date | None = None,
) -> Mantenimiento:
    requerir_permiso(actor, Permiso.MANTENIMIENTO_GESTIONAR)
    hoy = hoy or date.today()
    mantenimiento = obtener(session, Mantenimiento, mantenimiento_id)
    if mantenimiento.fecha_fin is not None:
        raise ReglaNegocioError("El mantenimiento ya está cerrado.")
    if costo < 0:
        raise ReglaNegocioError("El costo del mantenimiento no puede ser negativo.")
    if hoy < mantenimiento.fecha_inicio:
        raise ReglaNegocioError("La fecha de cierre no puede ser anterior a la de apertura.")
    transicionar(mantenimiento.equipo, EstadoEquipo.DISPONIBLE)
    mantenimiento.fecha_fin = hoy
    mantenimiento.costo = costo
    if notas and notas.strip():
        mantenimiento.descripcion += f"\n[Cierre] {notas.strip()}"
    session.commit()
    return mantenimiento


def historial_mantenimiento(session: Session, actor: Usuario, equipo_id: int) -> list[Mantenimiento]:
    requerir_permiso(actor, Permiso.MANTENIMIENTO_VER)
    obtener(session, Equipo, equipo_id)
    return list(session.scalars(
        select(Mantenimiento)
        .where(Mantenimiento.equipo_id == equipo_id)
        .order_by(Mantenimiento.fecha_inicio.desc(), Mantenimiento.id.desc())
    ))


def mantenimientos_abiertos(session: Session, actor: Usuario) -> list[Mantenimiento]:
    requerir_permiso(actor, Permiso.MANTENIMIENTO_VER)
    return list(session.scalars(
        select(Mantenimiento)
        .where(Mantenimiento.fecha_fin.is_(None))
        .order_by(Mantenimiento.fecha_inicio)
    ))
