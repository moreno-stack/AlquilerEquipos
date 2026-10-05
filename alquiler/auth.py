"""Autenticación con bcrypt y control de acceso por roles (spec §5)."""

import enum

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from alquiler.errors import CredencialesInvalidas, PermisoDenegado, ReglaNegocioError
from alquiler.models import Cliente, Rol, Usuario

MIN_CARACTERES = 8
MAX_BYTES = 72  # bcrypt ignora (o rechaza) lo que exceda 72 bytes
MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


class Permiso(str, enum.Enum):
    CATALOGO_VER = "catalogo.ver"
    PERFIL_PROPIO = "perfil.propio"
    EQUIPOS_GESTIONAR = "equipos.gestionar"
    EQUIPOS_ELIMINAR = "equipos.eliminar"
    CLIENTES_VER = "clientes.ver"
    CLIENTES_GESTIONAR = "clientes.gestionar"
    ALQUILERES_VER = "alquileres.ver"
    ALQUILERES_GESTIONAR = "alquileres.gestionar"
    DEVOLUCIONES_REGISTRAR = "devoluciones.registrar"
    MANTENIMIENTO_VER = "mantenimiento.ver"
    MANTENIMIENTO_GESTIONAR = "mantenimiento.gestionar"
    IA_VER = "ia.ver"
    IA_CONSULTAS = "ia.consultas"
    REPORTES_VER = "reportes.ver"
    USUARIOS_GESTIONAR = "usuarios.gestionar"


_SOLO_ADMIN = {
    Permiso.EQUIPOS_ELIMINAR,
    Permiso.IA_CONSULTAS,
    Permiso.REPORTES_VER,
    Permiso.USUARIOS_GESTIONAR,
}

PERMISOS_POR_ROL: dict[Rol, frozenset[Permiso]] = {
    Rol.ADMIN: frozenset(Permiso),
    Rol.EMPLEADO: frozenset(set(Permiso) - _SOLO_ADMIN),
    Rol.CLIENTE: frozenset({Permiso.CATALOGO_VER, Permiso.PERFIL_PROPIO}),
}

# Hash de relleno: si el usuario no existe se verifica contra él igualmente,
# para que el tiempo de respuesta no delate qué usernames existen.
_HASH_FICTICIO = bcrypt.hashpw(b"relleno-no-usado", bcrypt.gensalt()).decode()


# ---------------------------------------------------------------- contraseñas
def validar_password(plano: str) -> None:
    if len(plano) < MIN_CARACTERES:
        raise ReglaNegocioError(
            f"La contraseña debe tener al menos {MIN_CARACTERES} caracteres."
        )
    if len(plano.encode("utf-8")) > MAX_BYTES:
        raise ReglaNegocioError(
            f"La contraseña es demasiado larga (máximo {MAX_BYTES} bytes; "
            "las letras con tilde y la ñ ocupan 2)."
        )


def hash_password(plano: str) -> str:
    return bcrypt.hashpw(plano.encode("utf-8"), bcrypt.gensalt()).decode()


def verificar_password(plano: str, hash_: str) -> bool:
    datos = plano.encode("utf-8")
    if len(datos) > MAX_BYTES:
        return False
    return bcrypt.checkpw(datos, hash_.encode())


# ---------------------------------------------------------------- usuarios
def _normalizar(username: str) -> str:
    return username.strip().lower()


def crear_usuario(
    session: Session,
    username: str,
    password: str,
    rol: Rol,
    nombre_completo: str,
    cliente_id: int | None = None,
) -> Usuario:
    username = _normalizar(username)
    if not username:
        raise ReglaNegocioError("El nombre de usuario es obligatorio.")
    validar_password(password)
    if not nombre_completo.strip():
        raise ReglaNegocioError("El nombre completo es obligatorio.")
    if rol is Rol.CLIENTE and cliente_id is None:
        raise ReglaNegocioError("Un usuario con rol cliente debe estar vinculado a un cliente.")
    if rol is not Rol.CLIENTE and cliente_id is not None:
        raise ReglaNegocioError("Solo los usuarios con rol cliente se vinculan a un cliente.")
    if cliente_id is not None and session.get(Cliente, cliente_id) is None:
        raise ReglaNegocioError("El cliente indicado no existe.")
    if session.scalar(select(Usuario).where(Usuario.username == username)) is not None:
        raise ReglaNegocioError(f"El usuario '{username}' ya existe.")

    usuario = Usuario(
        username=username,
        password_hash=hash_password(password),
        rol=rol,
        nombre_completo=nombre_completo.strip(),
        cliente_id=cliente_id,
    )
    session.add(usuario)
    session.commit()
    return usuario


def autenticar(session: Session, username: str, password: str) -> Usuario:
    usuario = session.scalar(select(Usuario).where(Usuario.username == _normalizar(username)))
    hash_ = usuario.password_hash if usuario else _HASH_FICTICIO
    if not verificar_password(password, hash_) or usuario is None or not usuario.activo:
        raise CredencialesInvalidas(MENSAJE_CREDENCIALES)
    return usuario


def asegurar_admin_inicial(session: Session, password: str) -> Usuario | None:
    """Crea el usuario ``admin`` si no existe ningún administrador."""
    if session.scalar(select(Usuario).where(Usuario.rol == Rol.ADMIN)) is not None:
        return None
    return crear_usuario(session, "admin", password, Rol.ADMIN, "Administrador")


# ---------------------------------------------------------------- RBAC
def tiene_permiso(usuario: Usuario, permiso: Permiso) -> bool:
    # activo es None en objetos aún no guardados: solo False revoca el acceso.
    return usuario.activo is not False and permiso in PERMISOS_POR_ROL[usuario.rol]


def requerir_permiso(usuario: Usuario, permiso: Permiso) -> None:
    if not tiene_permiso(usuario, permiso):
        raise PermisoDenegado(f"No tiene permiso para realizar esta acción ({permiso.value}).")
