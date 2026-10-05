"""Secciones de la ventana principal y su permiso requerido (spec §5 y §8)."""

from dataclasses import dataclass

from alquiler.ui.logica.contexto import Contexto


@dataclass(frozen=True)
class Seccion:
    clave: str
    titulo: str
    permiso: str


SECCIONES: tuple[Seccion, ...] = (
    Seccion("inicio", "Inicio", "perfil.propio"),
    Seccion("equipos", "Equipos", "catalogo.ver"),
    Seccion("mantenimiento", "Mantenimiento", "mantenimiento.ver"),
    Seccion("clientes", "Clientes", "clientes.ver"),
    Seccion("alquileres", "Alquileres", "alquileres.ver"),
    Seccion("reservas", "Reservas", "alquileres.ver"),
    Seccion("reportes", "Reportes", "reportes.ver"),
    Seccion("analisis_ia", "Análisis IA", "ia.ver"),
    Seccion("consola_ia", "Consola IA", "ia.consultas"),
    Seccion("usuarios", "Usuarios", "usuarios.gestionar"),
    Seccion("perfil", "Mi perfil", "perfil.propio"),
)


def secciones_para(ctx: Contexto) -> list[Seccion]:
    return [s for s in SECCIONES if ctx.puede(s.permiso)]
