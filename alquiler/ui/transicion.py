"""Transición de inicio de sesión: de la portada al tablero (≈2,8 s, se puede saltar).

Igual que la cinemática de arranque, es una línea de tiempo determinista: ``escena(t)`` dice
qué se ve en el milisegundo ``t`` y la ventana solo lo pinta.
"""

from dataclasses import dataclass

DURACION = 2800  # ms
TRAMOS: dict[str, tuple[int, int]] = {
    "anillo": (0, 700),         # un anillo de escaneo recorre el logo
    "saludo": (250, 900),       # "Hola, <nombre>" se escribe letra por letra
    "pasos": (800, 2000),       # las verificaciones aparecen una tras otra
    "progreso": (800, 2200),    # barra de carga
    "fundido": (2300, 2800),    # el logo se acerca y todo se funde hacia el tablero
}
PASOS = 4


def tramo(nombre: str, t: float) -> float:
    """Avance (0-1) del tramo ``nombre`` en el milisegundo ``t``."""
    inicio, fin = TRAMOS[nombre]
    return min(1.0, max(0.0, (t - inicio) / (fin - inicio)))


@dataclass(frozen=True)
class Escena:
    t: float
    anillo: float     # vuelta del anillo de escaneo (0-1)
    saludo: str       # parte del saludo ya escrita
    pasos: int        # verificaciones visibles
    progreso: float   # barra de carga (0-1)
    fundido: float    # acercamiento y velo final (0-1)


def escena(t: float, nombre: str) -> Escena:
    saludo = f"Hola, {nombre}"
    return Escena(
        t=t,
        anillo=tramo("anillo", t),
        saludo=saludo[:round(len(saludo) * tramo("saludo", t))],
        pasos=min(PASOS, int(PASOS * tramo("pasos", t) * 1.2)),
        progreso=tramo("progreso", t),
        fundido=tramo("fundido", t),
    )


_ROLES = {"admin": "ADMINISTRADOR", "empleado": "EMPLEADO", "cliente": "CLIENTE"}


def pasos_sesion(rol: str, secciones: int, ia_configurada: bool) -> list[tuple[str, str]]:
    """Verificaciones que se muestran; todas describen el estado real (nada se finge)."""
    return [
        ("Identidad verificada", _ROLES.get(rol, rol.upper())),
        ("Permisos del rol", f"{secciones} {'SECCIÓN' if secciones == 1 else 'SECCIONES'}"),
        ("Asistente Cubi", "GROQ" if ia_configurada else "MODO LOCAL"),
        ("Tablero de control", "LISTO"),
    ]
