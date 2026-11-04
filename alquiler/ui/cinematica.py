"""Cinemática de arranque "encendido del sistema" (≈5,6 s, se puede saltar).

La secuencia es una línea de tiempo determinista: ``escena(t)`` dice qué se ve en el
milisegundo ``t`` y el widget solo lo pinta. Así cada fotograma se puede probar sin reloj.
"""

from dataclasses import dataclass

DURACION = 5600  # ms
TRAMOS: dict[str, tuple[int, int]] = {
    "rejilla": (0, 700),        # la rejilla en perspectiva aparece
    "red": (400, 1600),         # los nodos de la red de datos se encienden
    "cubo": (1200, 2600),       # el cubo del logo se traza arista por arista
    "nucleo": (2500, 2900),     # el núcleo de IA se enciende
    "destello": (2600, 3200),   # destello de luz (sube y baja)
    "titulo": (2800, 3800),     # el título se escribe letra por letra
    "arranque": (3200, 4800),   # líneas de arranque y barra de carga
    "fundido": (5000, 5600),    # fundido final hacia la portada
}


def tramo(nombre: str, t: float) -> float:
    """Avance (0-1) del tramo ``nombre`` en el milisegundo ``t``."""
    inicio, fin = TRAMOS[nombre]
    return min(1.0, max(0.0, (t - inicio) / (fin - inicio)))


NODOS = 48  # nodos de la red de datos


@dataclass(frozen=True)
class Escena:
    """Lo que se ve en un instante de la cinemática."""

    t: float
    rejilla: float          # opacidad de la rejilla (0-1)
    nodos: int              # nodos de la red ya encendidos


def escena(t: float) -> Escena:
    return Escena(
        t=t,
        rejilla=tramo("rejilla", t),
        nodos=round(NODOS * tramo("red", t)),
    )
