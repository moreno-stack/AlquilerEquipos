"""Diálogo de inicio de sesión."""

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from alquiler.errors import ReglaNegocioError
from alquiler.ui import widgets
from alquiler.ui.logica.contexto import iniciar_sesion


class LoginDialog(QDialog):
    def __init__(self, fabrica_sesion, config, cliente_llm, reloj, parent=None):
        super().__init__(parent)
        self._args = (fabrica_sesion, config)
        self._cliente_llm, self._reloj = cliente_llm, reloj
        self.contexto = None
        self.setWindowTitle("Alquiler de Equipos — Iniciar sesión")
        self.setMinimumWidth(360)

        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        exterior.setSpacing(0)
        self.franja_marca = QWidget()
        self.franja_marca.setObjectName("franjaMarca")
        capa_franja = QVBoxLayout(self.franja_marca)
        capa_franja.setContentsMargins(0, 0, 0, 0)
        capa_franja.setSpacing(0)
        capa_franja.addWidget(widgets.marca("Alquiler de Equipos"))
        submarca = QLabel("Sistema inteligente de alquiler")
        submarca.setObjectName("submarca")
        capa_franja.addWidget(submarca)
        exterior.addWidget(self.franja_marca)
        cuerpo = QWidget()
        exterior.addWidget(cuerpo)
        capa = QVBoxLayout(cuerpo)
        capa.setContentsMargins(28, 24, 28, 24)
        capa.addWidget(widgets.encabezado("Bienvenido", "Ingrese con su usuario del sistema."))
        formulario = QFormLayout()
        self.campo_usuario = QLineEdit()
        self.campo_password = QLineEdit()
        self.campo_password.setEchoMode(QLineEdit.EchoMode.Password)
        formulario.addRow("Usuario", self.campo_usuario)
        formulario.addRow("Contraseña", self.campo_password)
        capa.addLayout(formulario)
        self.etiqueta_error = QLabel()
        self.etiqueta_error.setObjectName("error")
        self.etiqueta_error.setWordWrap(True)
        capa.addWidget(self.etiqueta_error)
        self.boton_ingresar = widgets.boton("Ingresar", "primario", self._ingresar)
        self.boton_ingresar.setDefault(True)
        capa.addWidget(self.boton_ingresar)
        self.campo_password.returnPressed.connect(self._ingresar)

    def _ingresar(self):
        try:
            self.contexto = iniciar_sesion(*self._args, self.campo_usuario.text(),
                                           self.campo_password.text(),
                                           self._cliente_llm, self._reloj)
        except ReglaNegocioError as e:
            self.etiqueta_error.setText(str(e))
            self.campo_password.selectAll()
            return
        self.accept()
