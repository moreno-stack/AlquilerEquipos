"""Clientes: registro, perfil propio, bajas lógicas e historial."""

import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from alquiler import auth
from alquiler.auth import Permiso, requerir_permiso, tiene_permiso
from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import Alquiler, Cliente, EstadoAlquiler, Rol, Usuario
from alquiler.services import obtener

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CAMPOS_GESTION = {"nombre", "telefono", "email", "direccion"}
CAMPOS_PERFIL_PROPIO = {"telefono", "email", "direccion"}
_EN_CURSO = (EstadoAlquiler.RESERVADO, EstadoAlquiler.ACTIVO)


def _es_el_mismo_cliente(actor: Usuario, cliente_id: int) -> bool:
    return tiene_permiso(actor, Permiso.PERFIL_PROPIO) and actor.cliente_id == cliente_id


def _requerir_ver(actor: Usuario, cliente_id: int) -> None:
    if not (tiene_permiso(actor, Permiso.CLIENTES_VER) or _es_el_mismo_cliente(actor, cliente_id)):
        raise PermisoDenegado("No tiene permiso para consultar este cliente.")


def _limpiar(campos: dict) -> dict:
    """Normaliza y valida los campos de contacto; no modifica nada."""
    limpios = {k: (v.strip() if isinstance(v, str) else v) for k, v in campos.items()}
    for obligatorio in ("documento", "nombre", "telefono"):
        if obligatorio in limpios and not limpios[obligatorio]:
            raise ReglaNegocioError(f"El campo {obligatorio} es obligatorio.")
    for opcional in ("email", "direccion"):
        if opcional in limpios and not limpios[opcional]:
            limpios[opcional] = None
    if limpios.get("email") and not _EMAIL.match(limpios["email"]):
        raise ReglaNegocioError("El correo electrónico no es válido.")
    return limpios


def registrar_cliente(
    session: Session,
    actor: Usuario,
    documento: str,
    nombre: str,
    telefono: str,
    email: str | None = None,
    direccion: str | None = None,
) -> Cliente:
    requerir_permiso(actor, Permiso.CLIENTES_GESTIONAR)
    datos = _limpiar(dict(documento=documento, nombre=nombre, telefono=telefono,
                          email=email, direccion=direccion))
    if session.scalar(select(Cliente).where(Cliente.documento == datos["documento"])):
        raise ReglaNegocioError(f"Ya existe un cliente con el documento {datos['documento']}.")
    cliente = Cliente(**datos)
    session.add(cliente)
    session.commit()
    return cliente


def autoregistrar_cliente(
    session: Session,
    documento: str,
    nombre: str,
    telefono: str,
    username: str,
    password: str,
    email: str | None = None,
    direccion: str | None = None,
) -> Usuario:
    """Registro público desde la portada: crea el cliente y su usuario (solo rol cliente).

    Todo o nada: si algo no es válido no queda ni el cliente ni el usuario. Un documento que ya
    está registrado no se puede reclamar (daría acceso al historial de otra persona).
    """
    datos = _limpiar(dict(documento=documento, nombre=nombre, telefono=telefono,
                          email=email, direccion=direccion))
    if session.scalar(select(Cliente).where(Cliente.documento == datos["documento"])):
        raise ReglaNegocioError("Ya existe un cliente con ese documento; pida al personal "
                                "que le cree su usuario.")
    try:
        cliente = Cliente(**datos)
        session.add(cliente)
        session.flush()
        usuario = auth.crear_usuario(session, username, password, Rol.CLIENTE, datos["nombre"],
                                     cliente.id, confirmar=False)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return usuario


def actualizar_cliente(session: Session, actor: Usuario, cliente_id: int, **campos) -> Cliente:
    no_editables = set(campos) - CAMPOS_GESTION
    if tiene_permiso(actor, Permiso.CLIENTES_GESTIONAR):
        permitidos = CAMPOS_GESTION
    elif _es_el_mismo_cliente(actor, cliente_id):
        permitidos = CAMPOS_PERFIL_PROPIO
    else:
        raise PermisoDenegado("No tiene permiso para modificar este cliente.")
    if no_editables:
        raise ReglaNegocioError(f"No se pueden editar: {', '.join(sorted(no_editables))}.")
    if set(campos) - permitidos:
        raise PermisoDenegado("Solo puede modificar su teléfono, correo y dirección.")
    cliente = obtener(session, Cliente, cliente_id)
    for campo, valor in _limpiar(campos).items():
        setattr(cliente, campo, valor)
    session.commit()
    return cliente


def desactivar_cliente(session: Session, actor: Usuario, cliente_id: int) -> Cliente:
    requerir_permiso(actor, Permiso.CLIENTES_GESTIONAR)
    cliente = obtener(session, Cliente, cliente_id)
    en_curso = session.scalar(
        select(func.count()).where(Alquiler.cliente_id == cliente_id,
                                   Alquiler.estado.in_(_EN_CURSO))
    )
    if en_curso:
        raise ReglaNegocioError(
            "El cliente tiene alquileres reservados o activos; ciérrelos antes de desactivarlo."
        )
    cliente.activo = False
    if cliente.usuario is not None:
        cliente.usuario.activo = False  # un cliente dado de baja no entra al sistema
    session.commit()
    return cliente


def buscar_clientes(
    session: Session, actor: Usuario, texto: str | None = None, incluir_inactivos: bool = False
) -> list[Cliente]:
    requerir_permiso(actor, Permiso.CLIENTES_VER)
    consulta = select(Cliente).order_by(Cliente.nombre)
    if not incluir_inactivos:
        consulta = consulta.where(Cliente.activo.is_(True))
    if texto and texto.strip():
        patron = f"%{texto.strip().lower()}%"
        consulta = consulta.where(
            or_(func.lower(Cliente.nombre).like(patron), Cliente.documento.like(patron))
        )
    return list(session.scalars(consulta))


def obtener_cliente(session: Session, actor: Usuario, cliente_id: int) -> Cliente:
    _requerir_ver(actor, cliente_id)
    return obtener(session, Cliente, cliente_id)


def _alquileres(session: Session, cliente_id: int, estados=None) -> list[Alquiler]:
    consulta = (
        select(Alquiler)
        .where(Alquiler.cliente_id == cliente_id)
        .order_by(Alquiler.fecha_inicio.desc(), Alquiler.id.desc())
    )
    if estados:
        consulta = consulta.where(Alquiler.estado.in_(estados))
    return list(session.scalars(consulta))


def historial_cliente(session: Session, actor: Usuario, cliente_id: int) -> list[Alquiler]:
    _requerir_ver(actor, cliente_id)
    obtener(session, Cliente, cliente_id)
    return _alquileres(session, cliente_id)


def alquileres_activos_cliente(session: Session, actor: Usuario, cliente_id: int) -> list[Alquiler]:
    _requerir_ver(actor, cliente_id)
    obtener(session, Cliente, cliente_id)
    return _alquileres(session, cliente_id, _EN_CURSO)
