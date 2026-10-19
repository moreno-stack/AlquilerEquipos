"""Portada de ingreso: presentación del sistema y panel de vidrio con usuario y contraseña."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from alquiler import __version__
from alquiler.errors import ReglaNegocioError
from alquiler.ui import animacion, iconos, tema, widgets
from alquiler.ui.logica.contexto import iniciar_sesion

BENEFICIOS = [
    ("equipos", "Control de la flota en tiempo real",
     "Disponibilidad, alquileres, reservas y mantenimiento en un solo tablero."),
    ("analisis_ia", "Inteligencia artificial explicable",
     "Estimaciones con Groq que siempre dicen por qué recomiendan algo."),
    ("consola_ia", "Consultas en lenguaje natural",
     "Pregunte a sus datos como lo haría a una persona y obtenga reportes al instante."),
]


def _beneficio(icono: str, titulo: str, detalle: str) -> tuple[QWidget, QLabel]:
    fila = QWidget()
    capa = QHBoxLayout(fila)
    capa.setContentsMargins(0, 0, 0, 0)
    capa.setSpacing(14)
    caja = QLabel()
    caja.setObjectName("iconoBeneficio")
    caja.setFixedSize(42, 42)
    caja.setAlignment(Qt.AlignmentFlag.AlignCenter)
    caja.setPixmap(iconos.icono(icono, tema.PALETA["acento"]).pixmap(20, 20))
    textos = QVBoxLayout()
    textos.setSpacing(2)
    etiqueta = QLabel(titulo)
    etiqueta.setObjectName("tituloBeneficio")
    explicacion = QLabel(detalle)
    explicacion.setObjectName("detalleBeneficio")
    explicacion.setWordWrap(True)
    textos.addWidget(etiqueta)
    textos.addWidget(explicacion)
    capa.addWidget(caja, 0, Qt.AlignmentFlag.AlignTop)
    capa.addLayout(textos, 1)
    return fila, etiqueta


def _campo(icono: str, marcador: str) -> QLineEdit:
    campo = QLineEdit()
    campo.setObjectName("campoPortada")
    campo.setPlaceholderText(marcador)
    campo.addAction(iconos.icono(icono, tema.PALETA["texto_secundario"]),
                    QLineEdit.ActionPosition.LeadingPosition)
    return campo


class LoginDialog(QDialog):
    def __init__(self, fabrica_sesion, config, cliente_llm, reloj, parent=None):
        super().__init__(parent)
        self._args = (fabrica_sesion, config)
        self._cliente_llm, self._reloj = cliente_llm, reloj
        self.contexto = None
        self.animacion_error = None
        self._entrada: list = []
        self.setWindowTitle("Alquiler de Equipos — Bienvenido")
        self.setMinimumSize(960, 600)
        self.resize(1100, 680)

        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        self.fondo = widgets.FondoCosmico(fps=30)
        exterior.addWidget(self.fondo)
        capa = QHBoxLayout(self.fondo)
        capa.setContentsMargins(72, 48, 72, 48)
        capa.setSpacing(64)
        capa.addWidget(self._columna_marca(), 1)
        capa.addWidget(self._columna_ingreso(), 0, Qt.AlignmentFlag.AlignVCenter)

    # ---------------------------------------------------------------- presentación
    def _columna_marca(self) -> QWidget:
        self.columna_marca = QWidget()
        col = QVBoxLayout(self.columna_marca)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)
        col.addStretch(1)
        insignia = QLabel()
        insignia.setObjectName("insigniaPortada")
        insignia.setFixedSize(56, 56)
        insignia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        insignia.setPixmap(iconos.icono("equipos", tema.PALETA["sobre_acento"]).pixmap(28, 28))
        widgets.aplicar_brillo(insignia, "acento", alfa=120, radio=36)
        col.addWidget(insignia)
        col.addSpacing(6)
        antetitulo = QLabel("SISTEMA INTELIGENTE DE")
        antetitulo.setObjectName("antetituloPortada")
        col.addWidget(antetitulo)
        self.titulo = widgets.TextoDegradado("Alquiler de Equipos")
        self.titulo.setObjectName("tituloPortada")
        col.addWidget(self.titulo)
        lema = QLabel("Controle su flota, sus alquileres y sus clientes desde un solo centro de "
                      "control, con una IA que explica cada recomendación.")
        lema.setObjectName("lemaPortada")
        lema.setWordWrap(True)
        lema.setMaximumWidth(520)
        col.addWidget(lema)
        col.addSpacing(18)
        self.beneficios: list[QLabel] = []
        for icono, titulo, detalle in BENEFICIOS:
            fila, etiqueta = _beneficio(icono, titulo, detalle)
            fila.setMaximumWidth(520)
            col.addWidget(fila)
            self.beneficios.append(etiqueta)
        col.addStretch(1)
        pie = QLabel(f"v{__version__} · Nodo local · SQLite")
        pie.setObjectName("datoSistema")
        col.addWidget(pie)
        return self.columna_marca

    # ---------------------------------------------------------------- ingreso
    def _columna_ingreso(self) -> QWidget:
        self.panel = widgets.Panel("Bienvenido", "Ingrese con su usuario del sistema.")
        self.panel.setFixedWidth(400)
        self.panel.capa.setContentsMargins(32, 32, 32, 32)
        self.panel.capa.setSpacing(8)
        self.panel.etiqueta_titulo.setObjectName("tituloIngreso")
        widgets.aplicar_brillo(self.panel, "acento", alfa=55, radio=44)
        self.panel.capa.addSpacing(10)
        for texto, campo in (("USUARIO", "campo_usuario"), ("CONTRASEÑA", "campo_password")):
            etiqueta = QLabel(texto)
            etiqueta.setObjectName("tituloModulo")
            self.panel.capa.addWidget(etiqueta)
            if campo == "campo_usuario":
                self.campo_usuario = _campo("perfil", "Su nombre de usuario")
                self.panel.capa.addWidget(self.campo_usuario)
                self.panel.capa.addSpacing(6)
            else:
                self.campo_password = _campo("candado", "Su contraseña")
                self.campo_password.setEchoMode(QLineEdit.EchoMode.Password)
                self.panel.capa.addWidget(self.campo_password)
        self.etiqueta_error = QLabel()
        self.etiqueta_error.setObjectName("error")
        self.etiqueta_error.setWordWrap(True)
        self.panel.capa.addWidget(self.etiqueta_error)
        self.boton_ingresar = widgets.boton("INGRESAR", "primario", self._ingresar)
        self.boton_ingresar.setDefault(True)
        self.boton_ingresar.setMinimumHeight(44)
        self.boton_ingresar.setIcon(iconos.icono("salir", tema.PALETA["sobre_acento"]))
        self.boton_ingresar.setIconSize(QSize(18, 18))
        widgets.aplicar_brillo(self.boton_ingresar, "acento", alfa=70, radio=24)
        animacion.brillo_al_pasar(self.boton_ingresar)
        self.panel.capa.addWidget(self.boton_ingresar)
        nota = QLabel("Acceso por rol: administrador, empleado o cliente.")
        nota.setObjectName("detalleBeneficio")
        nota.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.panel.capa.addSpacing(4)
        self.panel.capa.addWidget(nota)
        self.campo_password.returnPressed.connect(self._ingresar)
        self.campo_usuario.returnPressed.connect(self.campo_password.setFocus)
        return self.panel

    def showEvent(self, evento):
        super().showEvent(evento)
        if not self._entrada:  # solo la primera vez: presentación y luego el panel
            self._entrada = animacion.escalonar([self.columna_marca, self.panel], paso=160) or [None]
        self.campo_usuario.setFocus()

    def _ingresar(self):
        try:
            self.contexto = iniciar_sesion(*self._args, self.campo_usuario.text(),
                                           self.campo_password.text(),
                                           self._cliente_llm, self._reloj)
        except ReglaNegocioError as e:
            self.etiqueta_error.setText(str(e))
            self.campo_password.selectAll()
            self.animacion_error = animacion.temblor(self.panel)
            return
        self.accept()
