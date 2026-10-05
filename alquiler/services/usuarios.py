"""Gestión de usuarios del sistema (solo administradores) y contraseña propia."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler import auth
from alquiler.auth import Permiso, requerir_permiso
from alquiler.errors import CredencialesInvalidas, ReglaNegocioError
from alquiler.models import Rol, Usuario
from alquiler.services import obtener


def crear_usuario(
    session: Session,
    actor: Usuario,
    username: str,
    password: str,
    rol: Rol,
    nombre_completo: str,
    cliente_id: int | None = None,
) -> Usuario:
    requerir_permiso(actor, Permiso.USUARIOS_GESTIONAR)
    return auth.crear_usuario(session, username, password, rol, nombre_completo, cliente_id)


def listar_usuarios(session: Session, actor: Usuario) -> list[Usuario]:
    requerir_permiso(actor, Permiso.USUARIOS_GESTIONAR)
    return list(session.scalars(select(Usuario).order_by(Usuario.username)))


def cambiar_estado_usuario(session: Session, actor: Usuario, usuario_id: int, activo: bool) -> Usuario:
    """Activa o desactiva una cuenta.

    Nadie puede desactivarse a sí mismo; como solo un admin activo puede usar
    esta operación, siempre queda al menos un administrador activo.
    """
    requerir_permiso(actor, Permiso.USUARIOS_GESTIONAR)
    usuario = obtener(session, Usuario, usuario_id)
    if not activo and usuario.id == actor.id:
        raise ReglaNegocioError("No puede desactivar su propio usuario.")
    usuario.activo = activo
    session.commit()
    return usuario


def cambiar_password(session: Session, actor: Usuario, actual: str, nueva: str) -> None:
    requerir_permiso(actor, Permiso.PERFIL_PROPIO)
    if not auth.verificar_password(actual, actor.password_hash):
        raise CredencialesInvalidas("La contraseña actual no es correcta.")
    auth.validar_password(nueva)
    actor.password_hash = auth.hash_password(nueva)
    session.commit()


def restablecer_password(session: Session, actor: Usuario, usuario_id: int, nueva: str) -> None:
    requerir_permiso(actor, Permiso.USUARIOS_GESTIONAR)
    usuario = obtener(session, Usuario, usuario_id)
    auth.validar_password(nueva)
    usuario.password_hash = auth.hash_password(nueva)
    session.commit()
