"""Cinemática de arranque "encendido del sistema" (≈5,6 s, se puede saltar).

La secuencia es una línea de tiempo determinista: ``escena(t)`` dice qué se ve en el
milisegundo ``t`` y el widget solo lo pinta. Así cada fotograma se puede probar sin reloj.
"""

from dataclasses import dataclass

from alquiler.ui import logo

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
ARISTAS = 12  # aristas del cubo del logo
TITULO = "ALQUILER DE EQUIPOS"
SUBTITULO = "SISTEMA INTELIGENTE · CENTRO DE CONTROL"


def orden_aristas() -> list[tuple[int, int]]:
    """Orden de trazado: primero las aristas del frente, al final las tres ocultas."""
    return [(i, j) for i, j, oculta in sorted(logo.aristas(), key=lambda a: a[2])]


@dataclass(frozen=True)
class Escena:
    """Lo que se ve en un instante de la cinemática."""

    t: float
    rejilla: float          # opacidad de la rejilla (0-1)
    nodos: int              # nodos de la red ya encendidos
    cubo: float             # aristas trazadas (0-12; la parte decimal es la que va a medias)
    nucleo: float           # brillo del núcleo de IA (0-1)
    destello: float         # destello de luz: sube y baja (0-1-0)
    titulo: str             # parte del título ya escrita
    subtitulo: str          # aparece entero cuando el título termina


def escena(t: float) -> Escena:
    return Escena(
        t=t,
        rejilla=tramo("rejilla", t),
        nodos=round(NODOS * tramo("red", t)),
        cubo=ARISTAS * tramo("cubo", t),
        nucleo=tramo("nucleo", t),
        titulo=TITULO[:int(len(TITULO) * tramo("titulo", t))],
        subtitulo=SUBTITULO if tramo("titulo", t) >= 1 else "",
        destello=1 - abs(2 * tramo("destello", t) - 1) if 0 < tramo("destello", t) < 1 else 0.0,
    )


GLITCH_MAX = 6  # px de separación entre las copias cian y púrpura del título


def glitch(t: float) -> int:
    """Desplazamiento del efecto glitch: a saltos mientras el título se escribe; 0 fuera."""
    if not 0 < tramo("titulo", t) < 1:
        return 0
    cuadro = int(t // 60)                       # cambia cada 60 ms, siempre igual
    ruido = (cuadro * 2654435761) % 1000 / 1000  # hash entero: sin azar entre ejecuciones
    return 0 if ruido < 0.35 else round((ruido - 0.675) / 0.325 * GLITCH_MAX)
