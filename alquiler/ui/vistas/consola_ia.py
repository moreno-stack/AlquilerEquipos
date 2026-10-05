"""Consola IA: preguntas en lenguaje natural con respuesta en dos partes.

(1) la respuesta directa y (2) cómo se obtuvo: pasos, SQL y datos. Todo corre en
segundo plano; mientras hay una consulta en curso no se aceptan otras.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import trabajador, widgets
from alquiler.ui.logica import ia
from alquiler.ui.logica.contexto import Contexto

TONO_ESTADO = {"ok": "ok", "sin_datos": "neutro", "aclaracion": "aviso", "no_resoluble": "aviso",
               "sin_api": "aviso", "error": "peligro"}
TITULO_A_ID = {titulo: id_ for id_, titulo in ia.PREDEFINIDAS}


def _subtitulo(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("etiquetaSeccion")
    return etiqueta


class VistaConsolaIA(QWidget):
    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.ocupado = False
        self._historial: list[dict] = []
        capa = QHBoxLayout(self)

        # ---- columna izquierda: consultas rápidas e historial
        izquierda = QVBoxLayout()
        izquierda.addWidget(widgets.encabezado("Consola IA"))
        izquierda.addWidget(_subtitulo("Consultas rápidas"))
        self.botones_predefinidas: dict[str, QPushButton] = {}
        for id_, titulo in ia.PREDEFINIDAS:
            b = widgets.boton(titulo, al_click=lambda _=False, i=id_: self.ejecutar_predefinida(i))
            b.setStyleSheet("text-align:left;")
            self.botones_predefinidas[id_] = b
            izquierda.addWidget(b)
        izquierda.addWidget(_subtitulo("Historial de esta sesión"))
        self.lista_historial = QListWidget()
        self.lista_historial.currentRowChanged.connect(self._ver_historial)
        izquierda.addWidget(self.lista_historial, 1)
        panel_izq = QWidget()
        panel_izq.setLayout(izquierda)
        panel_izq.setFixedWidth(290)
        capa.addWidget(panel_izq)

        # ---- columna derecha: pregunta y respuesta
        derecha = QVBoxLayout()
        self.aviso_sin_api = widgets.Insignia(
            "Sin GROQ_API_KEY: la IA no está configurada (agregue la clave en alquiler.env). "
            "Las consultas rápidas sí funcionan.",
            "aviso")
        self.aviso_sin_api.setVisible(not ia.ia_disponible(ctx))
        derecha.addWidget(self.aviso_sin_api)
        fila = QHBoxLayout()
        self.campo_pregunta = QLineEdit()
        self.campo_pregunta.setPlaceholderText(
            "Pregunte en lenguaje natural, p. ej. ¿Qué equipos tuvieron más alquileres este mes?")
        self.campo_pregunta.setMaxLength(500)
        self.campo_pregunta.returnPressed.connect(self.consultar)
        self.boton_consultar = widgets.boton("Consultar", "primario", self.consultar)
        fila.addWidget(self.campo_pregunta, 1)
        fila.addWidget(self.boton_consultar)
        derecha.addLayout(fila)

        self._panel = QFrame()
        self._panel.setObjectName("tarjeta")
        panel = QVBoxLayout(self._panel)
        cabecera = QHBoxLayout()
        self.etiqueta_estado = widgets.Insignia("Sin consultas todavía", "neutro")
        self.etiqueta_pregunta = QLabel()
        self.etiqueta_pregunta.setObjectName("subtituloVista")
        self.etiqueta_pregunta.setWordWrap(True)
        cabecera.addWidget(self.etiqueta_estado)
        cabecera.addWidget(self.etiqueta_pregunta, 1)
        panel.addLayout(cabecera)
        panel.addWidget(_subtitulo("1 · Respuesta"))
        self.etiqueta_respuesta = QLabel("Haga una pregunta o elija una consulta rápida.")
        self.etiqueta_respuesta.setWordWrap(True)
        self.etiqueta_respuesta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.etiqueta_respuesta.setStyleSheet("font-size:15px;")
        panel.addWidget(self.etiqueta_respuesta)
        panel.addWidget(_subtitulo("2 · Cómo se obtuvo"))
        self.lista_pasos = QListWidget()
        self.lista_pasos.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.lista_pasos.setWordWrap(True)
        self.lista_pasos.setMaximumHeight(110)
        self.lista_pasos.setStyleSheet("border:none; background:transparent;")
        panel.addWidget(self.lista_pasos)
        self.boton_sql = QToolButton()
        self.boton_sql.setText("Ver SQL ejecutado ▾")
        self.boton_sql.setObjectName("enlace")
        self.boton_sql.clicked.connect(self._alternar_sql)
        panel.addWidget(self.boton_sql, alignment=Qt.AlignmentFlag.AlignLeft)
        self.texto_sql = QPlainTextEdit()
        self.texto_sql.setReadOnly(True)
        self.texto_sql.setFont(QFont("Consolas, Menlo, monospace"))
        self.texto_sql.setMaximumHeight(90)
        self.texto_sql.hide()
        panel.addWidget(self.texto_sql)
        self.tabla_datos = widgets.Tabla()
        self.tabla_datos.setMinimumHeight(180)
        panel.addWidget(self.tabla_datos, 1)
        self.etiqueta_advertencia = QLabel()
        self.etiqueta_advertencia.setObjectName("advertencia")
        self.etiqueta_advertencia.setWordWrap(True)
        panel.addWidget(self.etiqueta_advertencia)
        self._fila_sugerencias = QHBoxLayout()
        panel.addLayout(self._fila_sugerencias)
        self.botones_sugerencias: list[QPushButton] = []

        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        desplazable.setWidget(self._panel)
        derecha.addWidget(desplazable, 1)
        capa.addLayout(derecha, 1)

    # ---------------------------------------------------------------- ejecución
    def _iniciar(self, trabajo, texto_estado: str) -> None:
        if self.ocupado:  # doble Enter / doble clic: se ignora
            return
        self.ocupado = True
        for b in [self.boton_consultar, *self.botones_predefinidas.values()]:
            b.setEnabled(False)
        self.etiqueta_estado.set_valor(texto_estado, "info")
        trabajador.ejecutar_en_segundo_plano(trabajo, self._recibir, self._fallo, self)

    def _terminar(self):
        self.ocupado = False
        for b in [self.boton_consultar, *self.botones_predefinidas.values()]:
            b.setEnabled(True)

    def consultar(self):
        texto = self.campo_pregunta.text().strip()
        if not texto:
            self.campo_pregunta.setFocus()
            return
        self._iniciar(lambda: ia.preguntar(self.ctx, texto), "Consultando a la IA…")

    def ejecutar_predefinida(self, id_: str):
        self._iniciar(lambda: ia.predefinida(self.ctx, id_), "Consultando…")

    def _recibir(self, respuesta: dict):
        self._terminar()
        self._historial.insert(0, respuesta)
        self.lista_historial.blockSignals(True)
        self.lista_historial.insertItem(0, QListWidgetItem(respuesta["pregunta"]))
        self.lista_historial.setCurrentRow(0)
        self.lista_historial.blockSignals(False)
        self.mostrar(respuesta)

    def _fallo(self, mensaje: str):
        self._terminar()
        self.mostrar({"estado": "error", "titulo_estado": ia.TITULO_ESTADO["error"],
                      "pregunta": self.campo_pregunta.text(), "respuesta": mensaje, "pasos": [],
                      "sql": "", "columnas": [], "filas": [], "advertencia": "", "sugerencias": []})

    def _ver_historial(self, fila: int):
        if 0 <= fila < len(self._historial):
            self.mostrar(self._historial[fila])

    # ---------------------------------------------------------------- presentación
    def mostrar(self, r: dict):
        self.etiqueta_estado.set_valor(r["titulo_estado"], TONO_ESTADO[r["estado"]])
        self.etiqueta_pregunta.setText(r["pregunta"])
        self.etiqueta_respuesta.setText(r["respuesta"])
        self.lista_pasos.clear()
        for i, paso in enumerate(r["pasos"], 1):
            self.lista_pasos.addItem(f"{i}. {paso}")
        if not r["pasos"]:
            self.lista_pasos.addItem("—")
        self.texto_sql.setPlainText(r["sql"])
        self.boton_sql.setVisible(bool(r["sql"]))
        self.texto_sql.hide()
        self.boton_sql.setText("Ver SQL ejecutado ▾")
        self.tabla_datos.cargar(r["columnas"], r["filas"])
        self.tabla_datos.setVisible(bool(r["columnas"]))
        self.etiqueta_advertencia.setText(r["advertencia"])
        for b in self.botones_sugerencias:
            b.deleteLater()
        self.botones_sugerencias = []
        for sugerencia in r["sugerencias"]:
            b = widgets.boton(sugerencia, al_click=lambda _=False, s=sugerencia: self._usar_sugerencia(s))
            self._fila_sugerencias.addWidget(b)
            self.botones_sugerencias.append(b)

    def _usar_sugerencia(self, texto: str):
        if texto in TITULO_A_ID:  # sin API: las sugerencias son las consultas rápidas
            self.ejecutar_predefinida(TITULO_A_ID[texto])
        else:
            self.campo_pregunta.setText(texto)
            self.campo_pregunta.setFocus()

    def _alternar_sql(self):
        visible = self.texto_sql.isHidden()
        self.texto_sql.setVisible(visible)
        self.boton_sql.setText("Ocultar SQL ▴" if visible else "Ver SQL ejecutado ▾")
