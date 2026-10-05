"""Errores de dominio. Sus mensajes están pensados para mostrarse al usuario."""


class ReglaNegocioError(Exception):
    """Una operación viola una regla de negocio."""


class CredencialesInvalidas(ReglaNegocioError):
    """Usuario o contraseña incorrectos, o usuario inactivo."""


class PermisoDenegado(ReglaNegocioError):
    """El usuario no tiene el permiso requerido para la operación."""
