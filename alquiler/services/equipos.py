"""Equipos, categorías y máquina de estados del equipo (spec §4.3)."""

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from alquiler.auth import Permiso, requerir_permiso, tiene_permiso
from alquiler.errors import ReglaNegocioError
from alquiler.models import Alquiler, Categoria, Equipo, EstadoEquipo, Mantenimiento, Usuario
from alquiler.services import obtener

E = EstadoEquipo
TRANSICIONES: dict[EstadoEquipo, frozenset[EstadoEquipo]] = {
    E.DISPONIBLE: frozenset({E.ALQUILADO, E.RESERVADO, E.EN_MANTENIMIENTO, E.FUERA_DE_SERVICIO}),
    E.RESERVADO: frozenset({E.DISPONIBLE, E.ALQUILADO}),
    E.ALQUILADO: frozenset({E.DISPONIBLE, E.EN_MANTENIMIENTO}),
    E.EN_MANTENIMIENTO: frozenset({E.DISPONIBLE, E.FUERA_DE_SERVICIO}),
    E.FUERA_DE_SERVICIO: frozenset({E.EN_MANTENIMIENTO}),
}

CAMPOS_EDITABLES = {"nombre", "descripcion", "categoria_id", "tarifa_diaria"}


def transicionar(equipo: Equipo, nuevo: EstadoEquipo) -> None:
    """Cambia el estado si la transición es válida. No hace commit."""
    if nuevo not in TRANSICIONES[equipo.estado]:
        raise ReglaNegocioError(
            f"Transición no permitida: {equipo.estado.value} → {nuevo.value}."
        )
    equipo.estado = nuevo


# ---------------------------------------------------------------- categorías
def crear_categoria(
    session: Session,
    actor: Usuario,
    nombre: str,
    descripcion: str | None = None,
    intervalo_mant_usos: int = 20,
    intervalo_mant_dias: int = 90,
) -> Categoria:
    requerir_permiso(actor, Permiso.EQUIPOS_GESTIONAR)
    nombre = nombre.strip()
    if not nombre:
        raise ReglaNegocioError("El nombre de la categoría es obligatorio.")
    if intervalo_mant_usos <= 0 or intervalo_mant_dias <= 0:
        raise ReglaNegocioError("Los intervalos de mantenimiento deben ser mayores que 0.")
    existe = session.scalar(
        select(Categoria).where(func.lower(Categoria.nombre) == nombre.lower())
    )
    if existe is not None:
        raise ReglaNegocioError(f"La categoría '{nombre}' ya existe.")
    categoria = Categoria(
        nombre=nombre,
        descripcion=descripcion,
        intervalo_mant_usos=intervalo_mant_usos,
        intervalo_mant_dias=intervalo_mant_dias,
    )
    session.add(categoria)
    session.commit()
    return categoria


def listar_categorias(session: Session, actor: Usuario) -> list[Categoria]:
    requerir_permiso(actor, Permiso.CATALOGO_VER)
    return list(session.scalars(select(Categoria).order_by(Categoria.nombre)))


# ---------------------------------------------------------------- equipos
def _validar_tarifa(tarifa_diaria: int) -> None:
    if tarifa_diaria <= 0:
        raise ReglaNegocioError("La tarifa diaria debe ser mayor que 0.")


def crear_equipo(
    session: Session,
    actor: Usuario,
    codigo: str,
    nombre: str,
    categoria_id: int,
    tarifa_diaria: int,
    fecha_adquisicion: date,
    descripcion: str | None = None,
) -> Equipo:
    requerir_permiso(actor, Permiso.EQUIPOS_GESTIONAR)
    codigo = codigo.strip().upper()
    nombre = nombre.strip()
    if not codigo or not nombre:
        raise ReglaNegocioError("El código y el nombre del equipo son obligatorios.")
    _validar_tarifa(tarifa_diaria)
    obtener(session, Categoria, categoria_id)
    if session.scalar(select(Equipo).where(Equipo.codigo == codigo)) is not None:
        raise ReglaNegocioError(f"Ya existe un equipo con el código {codigo}.")
    equipo = Equipo(
        codigo=codigo,
        nombre=nombre,
        descripcion=descripcion,
        categoria_id=categoria_id,
        tarifa_diaria=tarifa_diaria,
        fecha_adquisicion=fecha_adquisicion,
    )
    session.add(equipo)
    session.commit()
    return equipo


def actualizar_equipo(session: Session, actor: Usuario, equipo_id: int, **campos) -> Equipo:
    requerir_permiso(actor, Permiso.EQUIPOS_GESTIONAR)
    equipo = obtener(session, Equipo, equipo_id)
    no_permitidos = set(campos) - CAMPOS_EDITABLES
    if no_permitidos:
        raise ReglaNegocioError(f"No se pueden editar: {', '.join(sorted(no_permitidos))}.")
    if "tarifa_diaria" in campos:
        _validar_tarifa(campos["tarifa_diaria"])
    if "categoria_id" in campos:
        obtener(session, Categoria, campos["categoria_id"])
    if "nombre" in campos and not campos["nombre"].strip():
        raise ReglaNegocioError("El nombre del equipo es obligatorio.")
    for campo, valor in campos.items():
        setattr(equipo, campo, valor)
    session.commit()
    return equipo


def dar_de_baja(session: Session, actor: Usuario, equipo_id: int) -> Equipo:
    requerir_permiso(actor, Permiso.EQUIPOS_GESTIONAR)
    equipo = obtener(session, Equipo, equipo_id)
    transicionar(equipo, EstadoEquipo.FUERA_DE_SERVICIO)
    session.commit()
    return equipo


def eliminar_equipo(session: Session, actor: Usuario, equipo_id: int) -> None:
    requerir_permiso(actor, Permiso.EQUIPOS_ELIMINAR)
    equipo = obtener(session, Equipo, equipo_id)
    tiene_historial = (
        session.scalar(select(func.count()).where(Alquiler.equipo_id == equipo_id))
        or session.scalar(select(func.count()).where(Mantenimiento.equipo_id == equipo_id))
    )
    if tiene_historial:
        raise ReglaNegocioError(
            "El equipo tiene historial de alquileres o mantenimientos; "
            "páselo a 'Fuera de servicio' en lugar de eliminarlo."
        )
    session.delete(equipo)
    session.commit()


def listar_equipos(
    session: Session,
    actor: Usuario,
    estado: EstadoEquipo | None = None,
    categoria_id: int | None = None,
    texto: str | None = None,
) -> list[Equipo]:
    requerir_permiso(actor, Permiso.CATALOGO_VER)
    consulta = select(Equipo).order_by(Equipo.codigo)
    if not tiene_permiso(actor, Permiso.EQUIPOS_GESTIONAR):
        # Catálogo público: quien no gestiona equipos solo ve los disponibles.
        if estado not in (None, EstadoEquipo.DISPONIBLE):
            return []
        estado = EstadoEquipo.DISPONIBLE
    if estado is not None:
        consulta = consulta.where(Equipo.estado == estado)
    if categoria_id is not None:
        consulta = consulta.where(Equipo.categoria_id == categoria_id)
    if texto and texto.strip():
        patron = f"%{texto.strip().lower()}%"
        consulta = consulta.where(
            or_(func.lower(Equipo.codigo).like(patron), func.lower(Equipo.nombre).like(patron))
        )
    return list(session.scalars(consulta))
