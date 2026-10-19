"""Portada de ingreso: presentación del sistema y panel de vidrio con usuario y contraseña."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from alquiler import __version__
from alquiler.errors import ReglaNegocioError
from alquiler.ui import animacion, iconos, logo, tema, widgets
from alquiler.ui.logica.contexto import iniciar_sesion, registrar_y_entrar

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


def _rotulo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("tituloModulo")
    return etiqueta


def _etiqueta_error() -> QLabel:
    etiqueta = QLabel()
    etiqueta.setObjectName("error")
    etiqueta.setWordWrap(True)
    return etiqueta


def _enlace(texto: str, accion) -> QPushButton:
    enlace = QPushButton(texto)
    enlace.setObjectName("enlace")
    enlace.setCursor(Qt.CursorShape.PointingHandCursor)
    enlace.setFlat(True)
    enlace.setAutoDefault(False)
    enlace.clicked.connect(accion)
    return enlace


class LoginDialog(QDialog):
    def __init__(self, fabrica_sesion, config, cliente_llm, reloj, parent=None):
        super().__init__(parent)
        self._args = (fabrica_sesion, config)
        self._cliente_llm, self._reloj = cliente_llm, reloj
        self.contexto = None
        self.animacion_error = self.animacion_cambio = None
        self._entrada: list = []
        self.setWindowTitle("Alquiler de Equipos — Bienvenido")
        self.setWindowIcon(logo.icono_app())
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
        self.logo = logo.Logo(104)
        widgets.aplicar_brillo(self.logo, "acento", alfa=90, radio=40)
        col.addWidget(self.logo)
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
        self.panel.setFixedWidth(420)
        self.panel.capa.setContentsMargins(32, 30, 32, 28)
        self.panel.capa.setSpacing(8)
        self.panel.etiqueta_titulo.setObjectName("tituloIngreso")
        widgets.aplicar_brillo(self.panel, "acento", alfa=55, radio=44)
        self.panel.capa.addSpacing(8)
        self.pila_ingreso = QStackedWidget()
        self.vista_login = self._vista_login()
        self.vista_registro = self._vista_registro()
        self.pila_ingreso.addWidget(self.vista_login)
        self.pila_ingreso.addWidget(self.vista_registro)
        self.panel.capa.addWidget(self.pila_ingreso)
        self._ajustar_pila()
        return self.panel

    def _ajustar_pila(self) -> None:
        """El panel toma la altura de la vista visible (no la de la más alta)."""
        for i in range(self.pila_ingreso.count()):
            vista = self.pila_ingreso.widget(i)
            politica = (QSizePolicy.Policy.Preferred if vista is self.pila_ingreso.currentWidget()
                        else QSizePolicy.Policy.Ignored)
            vista.setSizePolicy(politica, politica)
        self.pila_ingreso.adjustSize()

    def _vista_login(self) -> QWidget:
        vista = QWidget()
        capa = QVBoxLayout(vista)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(8)
        self.campo_usuario = _campo("perfil", "Su nombre de usuario")
        self.campo_password = _campo("candado", "Su contraseña")
        self.campo_password.setEchoMode(QLineEdit.EchoMode.Password)
        for texto, campo in (("USUARIO", self.campo_usuario), ("CONTRASEÑA", self.campo_password)):
            capa.addWidget(_rotulo(texto))
            capa.addWidget(campo)
            capa.addSpacing(4)
        self.etiqueta_error = _etiqueta_error()
        capa.addWidget(self.etiqueta_error)
        self.boton_ingresar = self._boton_principal("INGRESAR", "salir", self._ingresar)
        self.boton_ingresar.setDefault(True)
        capa.addWidget(self.boton_ingresar)
        nota = QLabel("Acceso por rol: administrador, empleado o cliente.")
        nota.setObjectName("detalleBeneficio")
        nota.setAlignment(Qt.AlignmentFlag.AlignCenter)
        capa.addSpacing(4)
        capa.addWidget(nota)
        self.enlace_registro = _enlace("¿No tiene cuenta? Regístrese como cliente",
                                       lambda: self._mostrar(self.vista_registro))
        capa.addWidget(self.enlace_registro, 0, Qt.AlignmentFlag.AlignHCenter)
        self.campo_password.returnPressed.connect(self._ingresar)
        self.campo_usuario.returnPressed.connect(self.campo_password.setFocus)
        return vista

    def _vista_registro(self) -> QWidget:
        vista = QWidget()
        capa = QVBoxLayout(vista)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(6)
        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(12)
        rejilla.setVerticalSpacing(4)
        self.campos_registro: dict[str, QLineEdit] = {}
        # (clave, rótulo, ícono, marcador, fila, columna, columnas que ocupa)
        for clave, rotulo, icono, marcador, fila, col, ancho in (
                ("nombre", "NOMBRE COMPLETO", "clientes", "Nombre y apellidos", 0, 0, 2),
                ("documento", "DOCUMENTO", "perfil", "Cédula", 2, 0, 1),
                ("telefono", "TELÉFONO", "reloj", "Celular", 2, 1, 1),
                ("email", "CORREO (OPCIONAL)", "consola_ia", "nombre@correo.com", 4, 0, 2),
                ("usuario", "USUARIO", "perfil", "Con el que va a ingresar", 6, 0, 2),
                ("password", "CONTRASEÑA", "candado", "Mínimo 8 caracteres", 8, 0, 1),
                ("confirmacion", "CONFIRMAR", "candado", "Repítala", 8, 1, 1)):
            campo = _campo(icono, marcador)
            if clave in ("password", "confirmacion"):
                campo.setEchoMode(QLineEdit.EchoMode.Password)
            self.campos_registro[clave] = campo
            rejilla.addWidget(_rotulo(rotulo), fila, col, 1, ancho)
            rejilla.addWidget(campo, fila + 1, col, 1, ancho)
        capa.addLayout(rejilla)
        self.error_registro = _etiqueta_error()
        capa.addWidget(self.error_registro)
        self.boton_crear_cuenta = self._boton_principal("CREAR CUENTA", "clientes", self._registrar)
        capa.addWidget(self.boton_crear_cuenta)
        self.enlace_volver = _enlace("Ya tengo cuenta · Iniciar sesión",
                                     lambda: self._mostrar(self.vista_login))
        capa.addWidget(self.enlace_volver, 0, Qt.AlignmentFlag.AlignHCenter)
        self.campos_registro["confirmacion"].returnPressed.connect(self._registrar)
        return vista

    def _boton_principal(self, texto: str, icono: str, accion) -> QPushButton:
        boton = widgets.boton(texto, "primario", accion)
        boton.setMinimumHeight(44)
        boton.setIcon(iconos.icono(icono, tema.PALETA["sobre_acento"]))
        boton.setIconSize(QSize(18, 18))
        widgets.aplicar_brillo(boton, "acento", alfa=70, radio=24)
        animacion.brillo_al_pasar(boton)
        return boton

    def _mostrar(self, vista: QWidget) -> None:
        registro = vista is self.vista_registro
        self.panel.etiqueta_titulo.setText("Crear cuenta" if registro else "Bienvenido")
        self.panel.etiqueta_subtitulo.setText(
            "Regístrese como cliente para consultar el catálogo." if registro
            else "Ingrese con su usuario del sistema.")
        self.boton_crear_cuenta.setDefault(registro)
        self.boton_ingresar.setDefault(not registro)
        self.pila_ingreso.setCurrentWidget(vista)
        self._ajustar_pila()
        self.animacion_cambio = animacion.fundido_entrada(vista, ms=animacion.duracion("base"))
        (self.campos_registro["nombre"] if registro else self.campo_usuario).setFocus()

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

    def _registrar(self):
        valores = {clave: campo.text() for clave, campo in self.campos_registro.items()}
        try:
            self.contexto = registrar_y_entrar(
                *self._args, documento=valores["documento"], nombre=valores["nombre"],
                telefono=valores["telefono"], email=valores["email"], username=valores["usuario"],
                password=valores["password"], confirmacion=valores["confirmacion"],
                cliente_llm=self._cliente_llm, reloj=self._reloj)
        except ReglaNegocioError as e:
            self.error_registro.setText(str(e))
            self.animacion_error = animacion.temblor(self.panel)
            return
        self.accept()
