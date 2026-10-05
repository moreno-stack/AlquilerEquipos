"""Tema visual "Taller industrial" (spec Fase 6 §2): grafito, ámbar de seguridad y acero.

Es el ÚNICO archivo de ``alquiler.ui`` que escribe colores. Todo lo demás usa
estos tokens o los ``objectName`` que la hoja de estilo ya conoce. Todos los
pares texto/fondo cumplen WCAG AA (≥ 4,5:1), lo verifica ``tests/ui/test_tema.py``.
"""

PALETA: dict[str, str] = {
    "grafito": "#1E2630",          # barra lateral; texto sobre ámbar
    "grafito_claro": "#2A3440",    # elemento activo / hover de la barra lateral
    "texto_lateral": "#C9D1D9",
    "ambar": "#F2A900",            # marca, botón primario, indicador activo
    "ambar_hover": "#D99700",
    "ambar_suave": "#FFF4D6",
    "ambar_texto": "#7A5300",
    "acero": "#2F5D86",            # foco, enlaces, selección
    "acero_suave": "#E2ECF7",
    "arena": "#F5F3EE",            # fondo de la aplicación
    "superficie": "#FFFFFF",
    "borde": "#E4E1D9",
    "borde_fuerte": "#CFCAC0",
    "rejilla": "#EFECE6",
    "texto": "#1F2933",
    "texto_secundario": "#5F6B76",
    "peligro": "#B23A3A",
    "peligro_hover": "#962F2F",
    "deshabilitado": "#9AA3AB",
}

# estado del equipo -> (color fuerte, fondo de insignia, texto de insignia)
COLOR_ESTADO: dict[str, tuple[str, str, str]] = {
    "Disponible": ("#2E7D4F", "#E3F1E8", "#1F5C3A"),
    "Alquilado": ("#2F6DB5", "#E2ECF7", "#244F80"),
    "Reservado": ("#7A5AA6", "#EEE8F6", "#5A3F85"),
    "En mantenimiento": ("#C46A10", "#FBEBD9", "#8A4A0B"),
    "Fuera de servicio": ("#B23A3A", "#F6E1E1", "#8A2B2B"),
}

# tono semántico -> (fondo, texto); los de estado reutilizan los pares de COLOR_ESTADO
TONOS: dict[str, tuple[str, str]] = {
    "ok": COLOR_ESTADO["Disponible"][1:],
    "info": COLOR_ESTADO["Alquilado"][1:],
    "reserva": COLOR_ESTADO["Reservado"][1:],
    "aviso": COLOR_ESTADO["En mantenimiento"][1:],
    "peligro": COLOR_ESTADO["Fuera de servicio"][1:],
    "neutro": ("#ECEAE4", PALETA["texto"]),
    "marca": (PALETA["ambar_suave"], PALETA["ambar_texto"]),
}

# tono -> color fuerte (franjas de tarjetas, barras)
COLOR_TONO: dict[str, str] = {
    "ok": COLOR_ESTADO["Disponible"][0],
    "info": COLOR_ESTADO["Alquilado"][0],
    "reserva": COLOR_ESTADO["Reservado"][0],
    "aviso": COLOR_ESTADO["En mantenimiento"][0],
    "peligro": COLOR_ESTADO["Fuera de servicio"][0],
    "neutro": PALETA["borde_fuerte"],
    "marca": PALETA["ambar"],
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
QMainWindow, QDialog { background: {arena}; }
QToolTip { background: {grafito}; color: white; border: none; padding: 6px; }

/* barra lateral */
#panelLateral { background: {grafito}; }
#barraLateral { background: {grafito}; border: none; padding-top: 6px; outline: 0;
                show-decoration-selected: 0; }
#barraLateral::item { color: {texto_lateral}; padding: 11px 18px; margin: 1px 0;
                      border-left: 3px solid transparent; }
#barraLateral::item:selected { background: {grafito_claro}; color: white;
                               border-left: 3px solid {ambar}; }
#barraLateral::item:hover:!selected { background: {grafito_claro}; }
#marcaNombre { color: white; font-size: 13pt; font-weight: 700; }
#marcaCuadro { background: {ambar}; border-radius: 3px; }
#submarca { color: {texto_lateral}; font-size: 8pt; padding: 2px 18px 16px 42px; }
#franjaMarca { background: {grafito}; }


/* encabezados y textos */
#tituloVista { font-size: 18pt; font-weight: 600; color: {texto}; }
#subtituloVista { color: {texto_secundario}; }
#etiquetaSeccion { font-weight: 700; color: {texto_secundario}; margin-top: 10px; }
#advertencia { color: {texto_secundario}; font-style: italic; font-size: 9pt; }
#error { color: {peligro}; }
#notaInfo { background: {acero_suave}; color: {texto}; border-radius: 6px; padding: 8px;
            font-weight: 600; }

/* tarjetas */
#tarjeta, #kpi, #tarjetaKpi { background: {superficie}; border: 1px solid {borde};
                              border-radius: 10px; }
#kpiValor { font-size: 20pt; font-weight: 700; }
#kpiTitulo { color: {texto_secundario}; font-size: 9pt; }
#kpiDetalle { color: {texto_secundario}; font-size: 9pt; }
#tarjetaKpi[navegable="true"]:hover { border: 1px solid {borde_fuerte}; }
#saludo { font-size: 18pt; font-weight: 600; }

/* botones */
QPushButton { background: {superficie}; border: 1px solid {borde_fuerte}; border-radius: 6px;
              padding: 6px 16px; min-height: 20px; }
QPushButton:hover { background: {arena}; }
QPushButton:disabled { color: {deshabilitado}; background: {arena}; border-color: {borde}; }
QPushButton#primario { background: {ambar}; color: {grafito}; border: 1px solid {ambar};
                       font-weight: 600; }
QPushButton#primario:hover { background: {ambar_hover}; border-color: {ambar_hover}; }
QPushButton#primario:disabled { background: {ambar_suave}; color: {deshabilitado};
                                border-color: {ambar_suave}; }
QPushButton#peligro { background: {superficie}; color: {peligro}; border: 1px solid {peligro}; }
QPushButton#peligro:hover { background: {peligro}; color: white; }
QPushButton#peligro:disabled { background: {arena}; color: {deshabilitado}; border-color: {borde}; }
QPushButton#salir { background: transparent; color: {texto_lateral};
                    border: 1px solid {grafito_claro}; margin: 14px; }
QPushButton#salir:hover { background: {grafito_claro}; color: white; }
QToolButton#enlace, QPushButton#enlace { border: none; background: transparent; color: {acero};
                                         padding: 2px 0; }
QToolButton#enlace:hover, QPushButton#enlace:hover { text-decoration: underline; }

/* campos */
QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: {superficie}; border: 1px solid {borde_fuerte}; border-radius: 6px;
    padding: 5px 7px; selection-background-color: {acero}; selection-color: white; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus { border: 2px solid {acero}; padding: 4px 6px; }

/* tablas y listas */
QTableView { background: {superficie}; border: 1px solid {borde}; border-radius: 8px;
             gridline-color: {rejilla}; alternate-background-color: {arena};
             selection-background-color: {acero}; selection-color: white; }
QTableView::item { padding: 4px 6px; }
QHeaderView::section { background: {superficie}; border: none; border-bottom: 2px solid {borde};
                       padding: 7px 6px; font-weight: 600; color: {texto_secundario}; }
QListWidget { background: {superficie}; border: 1px solid {borde}; border-radius: 8px; }
QListWidget::item:selected { background: {acero}; color: white; }

/* pestañas, grupos y barra de estado */
QTabWidget::pane { border: none; }
QTabBar::tab { padding: 8px 16px; color: {texto_secundario}; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: {texto}; border-bottom: 2px solid {ambar}; font-weight: 600; }
QGroupBox { background: {superficie}; border: 1px solid {borde}; border-radius: 10px;
            margin-top: 14px; padding-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px;
                   color: {texto_secundario}; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
#lienzoInicio { background: {arena}; }
QStatusBar { background: {superficie}; border-top: 1px solid {borde}; }
QStatusBar QLabel { padding: 0 10px; color: {texto_secundario}; }
"""


def hoja_de_estilo() -> str:
    """QSS de la aplicación: cada ``{token}`` de la plantilla se sustituye por su color."""
    qss = _PLANTILLA
    for token, valor in PALETA.items():
        qss = qss.replace("{" + token + "}", valor)
    return qss
