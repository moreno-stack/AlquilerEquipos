"""Pantalla de Inicio (spec Fase 6 §3.3): saludo, indicadores por rol, flota y alerta de IA."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from alquiler.ui import trabajador, widgets
from alquiler.ui.logica import inicio
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import nivel
from alquiler.ui.logica.navegacion import secciones_para

COLUMNAS = 4


def _tarjeta_titulada(titulo: str) -> tuple[QFrame, QVBoxLayout]:
    marco = QFrame()
    marco.setObjectName("tarjeta")
    capa = QVBoxLayout(marco)
    capa.setContentsMargins(16, 14, 16, 16)
    capa.setSpacing(10)
    etiqueta = QLabel(titulo)
    etiqueta.setObjectName("etiquetaSeccion")
    etiqueta.setStyleSheet("margin-top: 0;")
    capa.addWidget(etiqueta)
    return marco, capa


class VistaInicio(QWidget):
    navegar = Signal(str)

    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._visibles = {s.clave for s in secciones_para(ctx)}
        self.tarjetas: list[widgets.TarjetaKPI] = []
        self.barra_estados: widgets.BarraEstados | None = None
        self.panel_alerta: QFrame | None = None
        self.boton_ver_analisis = None
        self.botones_acceso: dict = {}
        self.ocupado = False

        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.Shape.NoFrame)
        exterior.addWidget(desplazable)
        lienzo = QWidget()
        lienzo.setObjectName("lienzoInicio")
        desplazable.setWidget(lienzo)
        self._capa = QVBoxLayout(lienzo)
        self._capa.setContentsMargins(0, 0, 8, 8)
        self._capa.setSpacing(16)

        cabecera = QVBoxLayout()
        cabecera.setSpacing(2)
        self.etiqueta_saludo = QLabel()
        self.etiqueta_saludo.setObjectName("saludo")
        self.etiqueta_fecha = QLabel()
        self.etiqueta_fecha.setObjectName("subtituloVista")
        cabecera.addWidget(self.etiqueta_saludo)
        cabecera.addWidget(self.etiqueta_fecha)
        self._capa.addLayout(cabecera)

        self._contenido = QWidget()
        self._capa.addWidget(self._contenido)
        self._capa.addStretch(1)
        self.recargar()

    # ---------------------------------------------------------------- carga
    def recargar(self):
        if self.ocupado:
            return
        self.ocupado = True
        self.etiqueta_fecha.setText("Cargando…")
        trabajador.ejecutar_en_segundo_plano(
            lambda: inicio.resumen(self.ctx), self._mostrar, self._fallo, self)

    def al_volver(self):
        self.recargar()

    def _fallo(self, mensaje: str):
        self.ocupado = False
        self.etiqueta_fecha.setText("")
        widgets.mostrar_error(self, mensaje)

    def _mostrar(self, datos: dict):
        self.ocupado = False
        self.etiqueta_saludo.setText(datos["saludo"]["texto"])
        self.etiqueta_fecha.setText(datos["saludo"]["fecha"])
        nuevo = QWidget()
        capa = QVBoxLayout(nuevo)
        capa.setContentsMargins(0, 0, 0, 0)
        capa.setSpacing(16)

        rejilla = QGridLayout()
        rejilla.setSpacing(12)
        self.tarjetas = []
        for i, datos_tarjeta in enumerate(inicio.tarjetas_kpi(datos, self._visibles)):
            tarjeta = widgets.TarjetaKPI(datos_tarjeta)
            tarjeta.activada.connect(self.navegar)
            rejilla.addWidget(tarjeta, i // COLUMNAS, i % COLUMNAS)
            self.tarjetas.append(tarjeta)
        for columna in range(COLUMNAS):
            rejilla.setColumnStretch(columna, 1)
        capa.addLayout(rejilla)

        fila = QHBoxLayout()
        fila.setSpacing(12)
        self.barra_estados = None
        if "flota" in datos:
            marco, interior = _tarjeta_titulada("Estado de la flota")
            self.barra_estados = widgets.BarraEstados()
            self.barra_estados.cargar(datos["flota"]["conteos"])
            interior.addWidget(self.barra_estados)
            interior.addStretch(1)
            fila.addWidget(marco, 3)
        self.panel_alerta, self.boton_ver_analisis = None, None
        if "alerta_ia" in datos:
            alerta = datos["alerta_ia"]
            self.panel_alerta, interior = _tarjeta_titulada("Alertas de IA")
            texto = QLabel(alerta["texto"])
            texto.setWordWrap(True)
            texto.setStyleSheet("font-weight: 600;")
            interior.addWidget(texto)
            insignias = QHBoxLayout()
            insignias.addWidget(widgets.Insignia("Estimación", "info"))
            if alerta["confianza"]:
                insignias.addWidget(widgets.Insignia(f"Confianza {nivel(alerta['confianza'])}",
                                                     widgets.tono_para(alerta["confianza"])))
            insignias.addStretch(1)
            interior.addLayout(insignias)
            nota = QLabel("Puntaje por usos y días desde el último mantenimiento; "
                          "apoyo a la decisión, no una certeza.")
            nota.setObjectName("advertencia")
            nota.setWordWrap(True)
            interior.addWidget(nota)
            if "analisis_ia" in self._visibles:
                self.boton_ver_analisis = widgets.boton(
                    "Ver análisis", "primario", lambda: self.navegar.emit("analisis_ia"))
                interior.addWidget(self.boton_ver_analisis, 0, Qt.AlignmentFlag.AlignLeft)
            interior.addStretch(1)
            fila.addWidget(self.panel_alerta, 2)
        self.botones_acceso = {}
        if "mis_alquileres" in datos:
            marco, interior = _tarjeta_titulada("Accesos rápidos")
            ayuda = QLabel("Consulte el catálogo de equipos disponibles o revise su historial "
                           "de alquileres y sus datos de contacto.")
            ayuda.setObjectName("subtituloVista")
            ayuda.setWordWrap(True)
            interior.addWidget(ayuda)
            botones = QHBoxLayout()
            for clave, texto in (("equipos", "Ver equipos disponibles"), ("perfil", "Ir a Mi perfil")):
                if clave in self._visibles:
                    b = widgets.boton(texto, "", lambda _=False, c=clave: self.navegar.emit(c))
                    self.botones_acceso[clave] = b
                    botones.addWidget(b)
            botones.addStretch(1)
            interior.addLayout(botones)
            fila.addWidget(marco, 1)
        if fila.count():
            capa.addLayout(fila)

        self._capa.replaceWidget(self._contenido, nuevo)
        self._contenido.deleteLater()
        self._contenido = nuevo
