"""Diálogo "Conectar la IA": el administrador pega su clave de Groq, se prueba y se guarda."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from alquiler.ui import trabajador, widgets
from alquiler.ui.logica import ia
from alquiler.ui.logica.contexto import Contexto

PASOS = ("1. Entre a <a href='https://console.groq.com/keys'>console.groq.com/keys</a> y pulse "
         "<b>Create API Key</b>.<br>2. Copie la clave completa (empieza por <b>gsk_</b>).<br>"
         "3. Péguela aquí y pulse <b>Probar y conectar</b>.")


class DialogoConectarIA(QDialog):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.setWindowTitle("Conectar la IA (Groq)")
        self.setMinimumWidth(460)
        capa = QVBoxLayout(self)
        capa.addWidget(widgets.encabezado("Conectar la IA",
                                          "Activa el asistente Cubi y la Consola IA con Groq."))
        pasos = QLabel(PASOS)
        pasos.setWordWrap(True)
        pasos.setTextFormat(Qt.TextFormat.RichText)
        pasos.setOpenExternalLinks(True)
        capa.addWidget(pasos)
        self.campo_clave = QLineEdit()
        self.campo_clave.setPlaceholderText("gsk_…")
        self.campo_clave.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_clave.returnPressed.connect(self.conectar)
        capa.addWidget(self.campo_clave)
        mostrar = QCheckBox("Mostrar la clave")
        mostrar.toggled.connect(lambda ver: self.campo_clave.setEchoMode(
            QLineEdit.EchoMode.Normal if ver else QLineEdit.EchoMode.Password))
        capa.addWidget(mostrar)
        self.barra_carga = widgets.BarraCarga()
        capa.addWidget(self.barra_carga)
        self.etiqueta_error = QLabel()
        self.etiqueta_error.setObjectName("error")
        self.etiqueta_error.setWordWrap(True)
        capa.addWidget(self.etiqueta_error)
        nota = QLabel("La clave se guarda solo en este computador (carpeta .alquiler_equipos de "
                      "su usuario) y nunca se muestra completa.")
        nota.setObjectName("advertencia")
        nota.setWordWrap(True)
        capa.addWidget(nota)
        botones = QHBoxLayout()
        botones.addStretch(1)
        botones.addWidget(widgets.boton("Cancelar", al_click=self.reject))
        self.boton_conectar = widgets.boton("Probar y conectar", "primario", self.conectar)
        botones.addWidget(self.boton_conectar)
        capa.addLayout(botones)

    def conectar(self):
        clave = self.campo_clave.text()
        self.boton_conectar.setEnabled(False)
        self.etiqueta_error.setText("")
        self.barra_carga.iniciar()
        trabajador.ejecutar_en_segundo_plano(lambda: ia.conectar_ia(self.ctx, clave),
                                             self._listo, self._fallo, self)

    def _listo(self, _mensaje: str):
        self.barra_carga.detener()
        self.accept()

    def _fallo(self, mensaje: str):
        self.barra_carga.detener()
        self.boton_conectar.setEnabled(True)
        self.etiqueta_error.setText(mensaje)
