"""Tema visual "Pizarra y cian": fondo azul pizarra, acento cian y detalles violeta.

Los valores NO están aquí: se leen de ``diseno/tokens.css``, la única fuente de verdad
del sistema de diseño (documentado en ``diseno/DESIGN.md``), que también usa la página
de componentes ``diseno/styleguide.html``. Este módulo solo traduce esos tokens a Qt;
ningún archivo de ``alquiler.ui`` escribe un color a mano (lo verifican las pruebas).

``aplicar(app)`` activa el estilo Fusion con una paleta oscura, para que también
los elementos nativos (calendarios, menús, barras de desplazamiento) sean oscuros.
"""

import re
from pathlib import Path

from PySide6.QtGui import QColor, QPalette

# En el código fuente: <raíz>/diseno/tokens.css. Empaquetado: _internal/diseno/tokens.css
# (alquiler/ui/tema.py vive en _internal/alquiler/ui/, así que parents[2] es _internal).
RUTA_TOKENS = Path(__file__).resolve().parents[2] / "diseno" / "tokens.css"

_COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)
_DECLARACION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def leer_tokens(ruta: Path) -> dict[str, str]:
    """Variables CSS de ``ruta``; si una se redefine (p. ej. en @media), vale la primera."""
    texto = _COMENTARIO.sub("", ruta.read_text(encoding="utf-8"))
    tokens: dict[str, str] = {}
    for nombre, valor in _DECLARACION.findall(texto):
        tokens.setdefault(nombre, valor.strip())
    return tokens


# clave de Qt -> variable de tokens.css
MAPA_PALETA: dict[str, str] = {
    "fondo": "--color-fondo",
    "superficie": "--color-superficie",
    "superficie_alta": "--color-superficie-alta",
    "borde": "--color-borde",
    "borde_fuerte": "--color-borde-fuerte",
    "rejilla": "--color-rejilla",
    "texto": "--color-texto",
    "texto_secundario": "--color-texto-secundario",
    "lateral": "--color-fondo-hundido",
    "lateral_activo": "--color-superficie",
    "texto_lateral": "--color-texto-secundario",
    "acento": "--color-acento",
    "acento_hover": "--color-acento-hover",
    "sobre_acento": "--color-sobre-acento",
    "acento_suave": "--color-acento-suave",
    "acento_texto": "--color-acento-texto",
    "secundario": "--color-secundario",
    "secundario_claro": "--color-secundario-claro",
    "azul_electrico": "--color-azul-electrico",
    "purpura_neon": "--color-purpura-neon",
    "seleccion": "--color-seleccion",
    "peligro": "--color-peligro",
    "peligro_hover": "--color-peligro-fuerte",
    "deshabilitado": "--color-texto-deshabilitado",
    "blanco": "--color-blanco",
}
# estado del equipo -> prefijo de sus tres variables (--estado-<prefijo>-fuerte/fondo/texto)
PREFIJO_ESTADO: dict[str, str] = {
    "Disponible": "disponible", "Alquilado": "alquilado", "Reservado": "reservado",
    "En mantenimiento": "mantenimiento", "Fuera de servicio": "fuera",
}


def _token(tokens: dict[str, str], variable: str) -> str:
    if variable not in tokens:
        raise KeyError(f"Falta la variable {variable} en {RUTA_TOKENS.name}")
    return tokens[variable].upper()


def construir_paleta(tokens: dict[str, str]) -> dict[str, str]:
    return {clave: _token(tokens, variable) for clave, variable in MAPA_PALETA.items()}


def construir_estados(tokens: dict[str, str]) -> dict[str, tuple[str, str, str]]:
    return {estado: tuple(_token(tokens, f"--estado-{prefijo}-{parte}")
                          for parte in ("fuerte", "fondo", "texto"))
            for estado, prefijo in PREFIJO_ESTADO.items()}


TOKENS: dict[str, str] = leer_tokens(RUTA_TOKENS)
PALETA: dict[str, str] = construir_paleta(TOKENS)


def _degradado(inicio: str, fin: str) -> str:
    """Equivalente Qt de ``linear-gradient(135deg, inicio, fin)`` de tokens.css."""
    return f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {inicio}, stop:1 {fin})"


# Transparencias del vidrio esmerilado y los halos neón: se usan tal cual (rgba) en la QSS.
VIDRIO: dict[str, str] = {
    clave: TOKENS[variable] for clave, variable in (
        ("vidrio", "--color-vidrio"), ("vidrio_alto", "--color-vidrio-alto"),
        ("vidrio_borde", "--color-vidrio-borde"), ("neon_halo", "--color-neon-halo"),
        ("purpura_halo", "--color-purpura-halo"))
}


def qcolor(clave: str, alfa: int | None = None) -> QColor:
    """Color de la paleta como QColor, opcionalmente con transparencia (0-255)."""
    color = QColor(PALETA[clave])
    if alfa is not None:
        color.setAlpha(alfa)
    return color


# Degradado de marca (DESIGN.md §2.6): cian -> violeta, construido con los mismos tokens.
DEGRADADOS: dict[str, str] = {
    "degradado": _degradado(PALETA["acento"], PALETA["secundario"]),
    "degradado_hover": _degradado(PALETA["acento_hover"], PALETA["secundario_claro"]),
}
# estado del equipo -> (color fuerte, fondo de insignia, texto de insignia)
COLOR_ESTADO: dict[str, tuple[str, str, str]] = construir_estados(TOKENS)

# tono semántico -> (fondo, texto); los de estado reutilizan los pares de COLOR_ESTADO
TONOS: dict[str, tuple[str, str]] = {
    "ok": COLOR_ESTADO["Disponible"][1:],
    "info": COLOR_ESTADO["Alquilado"][1:],
    "reserva": COLOR_ESTADO["Reservado"][1:],
    "aviso": COLOR_ESTADO["En mantenimiento"][1:],
    "peligro": COLOR_ESTADO["Fuera de servicio"][1:],
    "neutro": (PALETA["borde"], PALETA["texto"]),
    "marca": (PALETA["acento_suave"], PALETA["acento_texto"]),
}

# tono -> color fuerte (franjas de tarjetas, barras)
COLOR_TONO: dict[str, str] = {
    "ok": COLOR_ESTADO["Disponible"][0],
    "info": COLOR_ESTADO["Alquilado"][0],
    "reserva": COLOR_ESTADO["Reservado"][0],
    "aviso": COLOR_ESTADO["En mantenimiento"][0],
    "peligro": COLOR_ESTADO["Fuera de servicio"][0],
    "neutro": PALETA["deshabilitado"],
    "marca": PALETA["acento"],
}


def _luminancia(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    canales = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canales)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    """Razón de contraste WCAG 2.x entre dos colores ``#RRGGBB`` (1 a 21)."""
    claro, oscuro = sorted((_luminancia(a), _luminancia(b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


_PLANTILLA = """
QWidget { font-size: 10pt; color: {texto}; }
QMainWindow, QDialog { background: {fondo}; }
QToolTip { background: {superficie_alta}; color: {texto}; border: 1px solid {borde_fuerte};
           padding: 6px; }
QLabel { background: transparent; }

/* menú lateral */
#panelLateral { background: {lateral}; border-right: 1px solid {vidrio_borde}; }
#barraLateral { background: {lateral}; border: none; padding-top: 6px; outline: 0;
                show-decoration-selected: 0; }
#barraLateral::item { color: {texto_lateral}; padding: 10px 14px; margin: 2px 10px;
                      border-radius: 8px; }
#barraLateral::item:selected { background: {degradado}; color: {sobre_acento}; font-weight: 700; }
#barraLateral::item:hover:!selected { background: {lateral_activo}; color: {texto}; }
#marca { background: transparent; }
#marcaCuadro { background: {degradado}; border-radius: 4px; }
#marcaNombre { color: {texto}; font-size: 13pt; font-weight: 700; }
#submarca { color: {texto_lateral}; font-size: 8pt; padding: 2px 18px 16px 42px; }

/* portada de ingreso */
#insigniaPortada { background: {degradado}; border-radius: 16px; }
#antetituloPortada { color: {acento}; font-size: 10pt; font-weight: 700; letter-spacing: 4px; }
#tituloPortada { font-size: 34pt; font-weight: 800; }
#lemaPortada { color: {texto_secundario}; font-size: 12pt; }
#iconoBeneficio { background: {acento_suave}; border: 1px solid {vidrio_borde}; border-radius: 12px; }
#tituloBeneficio { color: {texto}; font-size: 11pt; font-weight: 700; }
#detalleBeneficio { color: {texto_secundario}; font-size: 9pt; }
#tituloIngreso { font-size: 20pt; font-weight: 800; color: {texto}; }
QLineEdit#campoPortada { background: {vidrio_alto}; border: 1px solid {vidrio_borde}; border-radius: 10px;
                         min-height: 34px; padding: 4px 10px; }
QLineEdit#campoPortada:focus { border: 1px solid {acento}; }

/* encabezados y textos */
#tituloVista { font-size: 18pt; font-weight: 600; color: {texto}; }
#subtituloVista { color: {texto_secundario}; }
#etiquetaSeccion { font-weight: 700; color: {texto_secundario}; margin-top: 10px; }
#advertencia { color: {texto_secundario}; font-style: italic; font-size: 9pt; }
#error { color: {peligro}; }
#notaInfo { background: {acento_suave}; color: {acento_texto}; border-radius: 6px; padding: 8px;
            font-weight: 600; }

/* tarjetas */
#tarjeta, #kpi, #tarjetaKpi, #panelVidrio { background: {vidrio}; border: 1px solid {vidrio_borde};
                                            border-radius: 14px; }
#kpiValor { font-size: 20pt; font-weight: 700; color: {texto}; }
#kpiTitulo { color: {texto_secundario}; font-size: 9pt; }
#kpiDetalle { color: {texto_secundario}; font-size: 9pt; }
#tarjetaKpi[navegable="true"]:hover { border: 1px solid {acento}; background: {vidrio_alto}; }
#tituloModulo { color: {texto_secundario}; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }
#tituloPanel { font-size: 11pt; font-weight: 700; color: {texto}; }
#subtituloPanel { color: {texto_secundario}; font-size: 9pt; }
#estadoSistema { background: {vidrio}; border: 1px solid {vidrio_borde}; border-radius: 12px; }
#datoSistema { color: {texto_secundario}; font-size: 8pt; }
#valorSistema { color: {acento}; font-size: 8pt; font-weight: 700; }
QProgressBar#barraNeon { background: {superficie_alta}; border: none; border-radius: 3px; max-height: 6px;
                         min-height: 6px; }
QProgressBar#barraNeon::chunk { background: {degradado}; border-radius: 3px; }
QLineEdit#buscadorGlobal { background: {vidrio}; border: 1px solid {vidrio_borde}; border-radius: 10px;
                           padding: 7px 10px; min-width: 280px; }
QLineEdit#buscadorGlobal:focus { border: 1px solid {acento}; }
QTableView#monitor { background: transparent; border: none; alternate-background-color: {vidrio_alto};
                     gridline-color: transparent; }
QTableView#monitor QHeaderView::section { background: transparent; border-bottom: 1px solid {vidrio_borde};
                                          font-size: 8pt; letter-spacing: 1px; }
#saludo { font-size: 18pt; font-weight: 600; }
#lienzoInicio { background: transparent; }

/* botones */
QPushButton { background: {superficie_alta}; color: {texto}; border: 1px solid {borde_fuerte};
              border-radius: 8px; padding: 7px 16px; min-height: 20px; }
QPushButton:hover { background: {borde}; border-color: {texto_secundario}; }
QPushButton:pressed { background: {borde_fuerte}; }
QPushButton:disabled { color: {deshabilitado}; background: {superficie}; border-color: {borde}; }
QPushButton#primario { background: {degradado}; color: {sobre_acento}; border: none;
                       font-weight: 700; padding: 8px 17px; }
QPushButton#primario:hover { background: {degradado_hover}; }
QPushButton#primario:disabled { background: {acento_suave}; color: {deshabilitado};
                                border-color: {acento_suave}; }
QPushButton#peligro { background: transparent; color: {peligro}; border: 1px solid {peligro}; }
QPushButton#peligro:hover { background: {peligro_hover}; color: {blanco}; border-color: {peligro_hover}; }
QPushButton#peligro:disabled { color: {deshabilitado}; border-color: {borde}; }
QPushButton#salir { background: transparent; color: {texto_lateral}; border: 1px solid {borde};
                    margin: 14px; text-align: left; padding-left: 14px; }
QPushButton#salir:hover { background: {lateral_activo}; color: {peligro}; border-color: {peligro}; }
QToolButton#enlace, QPushButton#enlace { border: none; background: transparent; color: {acento};
                                         padding: 2px 0; }
QToolButton#enlace:hover, QPushButton#enlace:hover { text-decoration: underline; }

/* campos */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: {superficie}; color: {texto}; border: 1px solid {borde_fuerte}; border-radius: 8px;
    padding: 5px 8px; selection-background-color: {seleccion}; selection-color: {blanco}; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus { border: 2px solid {acento}; padding: 4px 7px; }
QLineEdit:disabled, QComboBox:disabled { color: {deshabilitado}; }
QComboBox QAbstractItemView { background: {superficie}; color: {texto}; border: 1px solid {borde_fuerte};
                              selection-background-color: {seleccion}; selection-color: {blanco};
                              outline: 0; }
QCheckBox, QRadioButton { background: transparent; }
QCalendarWidget QWidget { background: {superficie}; color: {texto};
                          alternate-background-color: {superficie_alta}; }
QCalendarWidget QToolButton { background: transparent; color: {texto}; border: none; padding: 4px; }
QCalendarWidget QAbstractItemView:enabled { selection-background-color: {seleccion};
                                            selection-color: {blanco}; }
QCalendarWidget QAbstractItemView:disabled { color: {deshabilitado}; }
QMenu { background: {superficie}; color: {texto}; border: 1px solid {borde_fuerte}; }
QMenu::item:selected { background: {seleccion}; color: {blanco}; }

/* tablas y listas */
QTableView { background: {superficie}; color: {texto}; border: 1px solid {borde}; border-radius: 10px;
             gridline-color: {rejilla}; alternate-background-color: {superficie_alta};
             selection-background-color: {seleccion}; selection-color: {blanco}; }
QTableView::item { padding: 4px 6px; }
QHeaderView::section { background: {superficie}; color: {texto_secundario}; border: none;
                       border-bottom: 2px solid {borde}; padding: 8px 6px; font-weight: 600; }
QTableCornerButton::section { background: {superficie}; border: none; }
QListWidget { background: {superficie}; color: {texto}; border: 1px solid {borde};
              border-radius: 10px; }
QListWidget::item:selected { background: {seleccion}; color: {blanco}; }

/* barras de desplazamiento */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle { background: {borde_fuerte}; border-radius: 4px; min-height: 24px; min-width: 24px; }
QScrollBar::handle:hover { background: {texto_secundario}; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

/* pestañas, grupos y barra de estado */
QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; padding: 8px 16px; color: {texto_secundario};
               border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: {texto}; border-bottom: 2px solid {acento}; font-weight: 600; }
QTabBar::tab:hover:!selected { color: {secundario}; }
QGroupBox { background: {superficie}; border: 1px solid {borde}; border-radius: 12px;
            margin-top: 14px; padding-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px;
                   color: {texto_secundario}; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QStatusBar { background: {lateral}; border-top: 1px solid {borde}; }
QStatusBar QLabel { padding: 0 10px; color: {texto_secundario}; }
QMessageBox, QInputDialog { background: {fondo}; }
#avisoCarga { background: {superficie}; color: {texto}; padding: 24px; font-size: 14px;
              border: 1px solid {borde_fuerte}; }
"""


def hoja_de_estilo() -> str:
    """QSS de la aplicación: cada ``{token}`` de la plantilla se sustituye por su color."""
    qss = _PLANTILLA
    for token, valor in sorted({**PALETA, **DEGRADADOS, **VIDRIO}.items(), key=lambda kv: -len(kv[0])):
        qss = qss.replace("{" + token + "}", valor)
    return qss


def paleta_qt() -> QPalette:
    """Paleta oscura de Qt para lo que la hoja de estilo no alcanza (diálogos nativos, etc.)."""
    p = QPalette()
    roles = QPalette.ColorRole
    for rol, token in ((roles.Window, "fondo"), (roles.WindowText, "texto"), (roles.Base, "superficie"),
                       (roles.AlternateBase, "superficie_alta"), (roles.Text, "texto"),
                       (roles.Button, "superficie_alta"), (roles.ButtonText, "texto"),
                       (roles.ToolTipBase, "superficie_alta"), (roles.ToolTipText, "texto"),
                       (roles.Highlight, "seleccion"), (roles.HighlightedText, "blanco"),
                       (roles.Link, "acento"), (roles.PlaceholderText, "deshabilitado"),
                       (roles.BrightText, "blanco")):
        p.setColor(rol, QColor(PALETA[token]))
    for rol in (roles.Text, roles.WindowText, roles.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, rol, QColor(PALETA["deshabilitado"]))
    return p


def aplicar(aplicacion) -> None:
    """Fusion + paleta oscura + hoja de estilo: el aspecto completo de la aplicación."""
    aplicacion.setStyle("Fusion")
    aplicacion.setPalette(paleta_qt())
    aplicacion.setStyleSheet(hoja_de_estilo())
