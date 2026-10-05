"""Capa de servicios: reglas de negocio y autorización (spec §3).

Contrato: ``op(session, actor, ...)`` verifica el permiso, valida todas las
reglas y solo entonces modifica y hace commit.
"""

from sqlalchemy.orm import Session

from alquiler.errors import ReglaNegocioError
from alquiler.models import Alquiler, Categoria, Cliente, Equipo, Mantenimiento, Usuario

_NOMBRES = {
    Equipo: "Equipo",
    Categoria: "Categoría",
    Cliente: "Cliente",
    Alquiler: "Alquiler",
    Mantenimiento: "Mantenimiento",
    Usuario: "Usuario",
}


def pesos(monto: int) -> str:
    """Formato COP para mensajes: 1234567 → '$1.234.567'."""
    return "$" + f"{monto:,}".replace(",", ".")


def obtener(session: Session, modelo, id_):
    objeto = session.get(modelo, id_)
    if objeto is None:
        raise ReglaNegocioError(f"{_NOMBRES[modelo]} no existe.")
    return objeto
