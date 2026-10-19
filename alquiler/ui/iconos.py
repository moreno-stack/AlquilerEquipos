"""Iconos vectoriales del menú (trazos estilo Tabler Icons, licencia MIT), sin archivos externos.

Cada icono es el contenido de un SVG de 24×24 con trazo ``currentColor``. ``icono()``
lo dibuja con QtSvg en dos colores: el normal y el de la sección seleccionada.
"""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

SVG: dict[str, str] = {
    "inicio": '<path d="M5 12l-2 0l9 -9l9 9l-2 0"/><path d="M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-7"/>'
              '<path d="M9 21v-6a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2v6"/>',
    "equipos": '<path d="M12 3l8 4.5l0 9l-8 4.5l-8 -4.5l0 -9l8 -4.5"/><path d="M12 12l8 -4.5"/>'
               '<path d="M12 12l0 9"/><path d="M12 12l-8 -4.5"/>',
    "mantenimiento": '<path d="M7 10h3v-3l-3.5 -3.5a6 6 0 0 1 8 8l6 6a2 2 0 0 1 -3 3l-6 -6'
                     'a6 6 0 0 1 -8 -8l3.5 3.5"/>',
    "clientes": '<path d="M5 7a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/><path d="M3 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2"/>'
                '<path d="M16 3.13a4 4 0 0 1 0 7.75"/><path d="M21 21v-2a4 4 0 0 0 -3 -3.85"/>',
    "alquileres": '<path d="M14 3v4a1 1 0 0 0 1 1h4"/>'
                  '<path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z"/>'
                  '<path d="M9 9l1 0"/><path d="M9 13l6 0"/><path d="M9 17l6 0"/>',
    "reservas": '<path d="M4 7a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12z"/>'
                '<path d="M16 3v4"/><path d="M8 3v4"/><path d="M4 11h16"/><path d="M8 15h2v2h-2z"/>',
    "reportes": '<path d="M3 13a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v6a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1z"/>'
                '<path d="M15 9a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v10a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1z"/>'
                '<path d="M9 5a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v14a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1z"/>',
    "analisis_ia": '<path d="M3 12h1m8 -9v1m8 8h1m-15.4 -6.4l.7 .7m12.1 -.7l-.7 .7"/>'
                   '<path d="M9 16a5 5 0 1 1 6 0a3.5 3.5 0 0 0 -1 3a2 2 0 0 1 -4 0a3.5 3.5 0 0 0 -1 -3"/>'
                   '<path d="M9.7 17l4.6 0"/>',
    "consola_ia": '<path d="M8 9h8"/><path d="M8 13h6"/>'
                  '<path d="M18 4a3 3 0 0 1 3 3v8a3 3 0 0 1 -3 3h-5l-5 3v-3h-2a3 3 0 0 1 -3 -3v-8'
                  'a3 3 0 0 1 3 -3h12z"/>',
    "usuarios": '<path d="M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3"/>'
                '<path d="M10 11a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M12 13v2.5"/>',
    "perfil": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M9 10a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/>'
              '<path d="M6.168 18.849a4 4 0 0 1 3.832 -2.849h4a4 4 0 0 1 3.835 2.855"/>',
    "dinero": '<path d="M16.7 8a3 3 0 0 0 -2.7 -2h-4a3 3 0 0 0 0 6h4a3 3 0 0 1 0 6h-4a3 3 0 0 1 -2.7 -2"/>'
              '<path d="M12 3v3m0 12v3"/>',
    "alerta": '<path d="M12 9v4"/><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214'
              'a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z"/><path d="M12 16h.01"/>',
    "reloj": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/><path d="M12 7v5l3 3"/>',
    "buscar": '<path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M21 21l-6 -6"/>',
    "diagnostico": '<path d="M3 12h4l3 8l4 -16l3 8h4"/>',
    "sube": '<path d="M3 17l6 -6l4 4l8 -8"/><path d="M14 7l7 0l0 7"/>',
    "salir": '<path d="M14 8v-2a2 2 0 0 0 -2 -2h-7a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h7a2 2 0 0 0 2 -2v-2"/>'
             '<path d="M9 12h12l-3 -3"/><path d="M18 15l3 -3"/>',
    "candado": '<path d="M5 13a2 2 0 0 1 2 -2h10a2 2 0 0 1 2 2v6a2 2 0 0 1 -2 2h-10a2 2 0 0 1 -2 -2v-6z"/>'
               '<path d="M11 16a1 1 0 1 0 2 0a1 1 0 0 0 -2 0"/><path d="M8 11v-4a4 4 0 1 1 8 0v4"/>',
}

_PLANTILLA = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{trazos}</svg>')
_TAMANOS = (16, 20, 24, 32, 48)


def _pixmap(nombre: str, color: str, lado: int) -> QPixmap:
    svg = _PLANTILLA.format(color=color, trazos=SVG[nombre])
    renderizador = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(lado, lado)
    pixmap.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(pixmap)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor, QRectF(0, 0, lado, lado))
    pintor.end()
    return pixmap


def icono(nombre: str, color: str, color_activo: str | None = None) -> QIcon:
    """Icono ``nombre`` en ``color``; ``color_activo`` para la sección seleccionada o el hover."""
    if nombre not in SVG:
        raise KeyError(f"No hay icono llamado {nombre!r}")
    resultado = QIcon()
    for lado in _TAMANOS:
        resultado.addPixmap(_pixmap(nombre, color, lado), QIcon.Mode.Normal)
        resultado.addPixmap(_pixmap(nombre, color_activo or color, lado), QIcon.Mode.Selected)
        resultado.addPixmap(_pixmap(nombre, color_activo or color, lado), QIcon.Mode.Active)
    return resultado
