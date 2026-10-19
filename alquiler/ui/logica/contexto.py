"""Contexto de la sesión de interfaz: una sesión de base de datos por operación.

``Contexto.ejecutar(fn)`` abre una sesión, recarga al usuario, ejecuta ``fn``,
hace rollback ante cualquier excepción y siempre cierra. Así un fallo nunca
deja escrituras a medias ni "envenena" la siguiente operación.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from alquiler.auth import PERMISOS_POR_ROL, autenticar
from alquiler.config import Config
from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import Usuario

T = TypeVar("T")


@dataclass(frozen=True)
class UsuarioSesion:
    id: int
    username: str
    nombre: str
    rol: str
    cliente_id: int | None
    permisos: frozenset[str]

    @classmethod
    def desde(cls, usuario: Usuario) -> "UsuarioSesion":
        return cls(
            id=usuario.id,
            username=usuario.username,
            nombre=usuario.nombre_completo,
            rol=usuario.rol.value,
            cliente_id=usuario.cliente_id,
            permisos=frozenset(p.value for p in PERMISOS_POR_ROL[usuario.rol]),
        )


class Contexto:
    def __init__(self, fabrica_sesion: sessionmaker[Session], usuario: UsuarioSesion,
                 config: Config, cliente_llm=None, reloj: Callable[[], date] = date.today):
        self._fabrica = fabrica_sesion
        self.usuario = usuario
        self.config = config
        self.cliente_llm = cliente_llm
        self._reloj = reloj

    def hoy(self) -> date:
        return self._reloj()

    def puede(self, permiso: str) -> bool:
        return permiso in self.usuario.permisos

    def ejecutar(self, fn: Callable[[Session, Usuario], T]) -> T:
        sesion = self._fabrica()
        try:
            actor = sesion.scalar(select(Usuario).where(Usuario.id == self.usuario.id))
            if actor is None or not actor.activo:
                raise PermisoDenegado("La sesión ya no es válida; vuelva a iniciar sesión.")
            return fn(sesion, actor)
        except BaseException:
            sesion.rollback()
            raise
        finally:
            sesion.close()


def iniciar_sesion(fabrica_sesion: sessionmaker[Session], config: Config, username: str,
                   password: str, cliente_llm=None,
                   reloj: Callable[[], date] = date.today) -> Contexto:
    with fabrica_sesion() as sesion:
        usuario = UsuarioSesion.desde(autenticar(sesion, username, password))
    return Contexto(fabrica_sesion, usuario, config, cliente_llm, reloj)


def registrar_y_entrar(fabrica_sesion: sessionmaker[Session], config: Config, *, documento: str,
                       nombre: str, telefono: str, email: str, username: str, password: str,
                       confirmacion: str, cliente_llm=None,
                       reloj: Callable[[], date] = date.today) -> Contexto:
    """Crea la cuenta de cliente desde la portada y abre su sesión."""
    from alquiler.services.clientes import autoregistrar_cliente
    if password != confirmacion:
        raise ReglaNegocioError("Las contraseñas no coinciden.")
    with fabrica_sesion() as sesion:
        usuario = UsuarioSesion.desde(autoregistrar_cliente(
            sesion, documento, nombre, telefono, username, password, email=email or None))
    return Contexto(fabrica_sesion, usuario, config, cliente_llm, reloj)
