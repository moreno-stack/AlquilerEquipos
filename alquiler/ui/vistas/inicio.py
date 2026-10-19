"""Pantalla de Inicio con estilo "centro de control" (spec Fase 6 §3.3 + rediseño de interfaz).

Tablero de vidrio esmerilado sobre el fondo cósmico de la ventana:
indicadores con ícono, tendencia de alquileres, utilización de la flota (dona), ocupación por
categoría, alerta de IA y monitor de actividad. Los datos vienen de ``logica.inicio``.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from alquiler.ui import animacion, tema, trabajador, widgets
from alquiler.ui.logica import inicio
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.logica.formato import nivel
from alquiler.ui.logica.navegacion import secciones_para

COLUMNAS = 4
ICONO_KPI = {
    "disponibles": "equipos", "activos": "alquileres", "vencidos": "alerta", "vencen_hoy": "reloj",
    "reservas": "reservas", "mantenimiento": "mantenimiento", "ingresos": "dinero",
    "mis_activos": "alquileres", "mi_saldo": "dinero",
}
COLUMNAS_MONITOR = [("fecha", "FECHA"), ("modulo", "MÓDULO"), ("mensaje", "MENSAJE"), ("estado", "ESTADO")]


def _panel(titulo: str, subtitulo: str = "") -> widgets.Panel:
    panel = widgets.Panel(titulo, subtitulo)
    widgets.aplicar_brillo(panel, "acento", alfa=30, radio=30)
    return panel


class VistaInicio(QWidget):
    navegar = Signal(str)

    def __init__(self, ctx: Contexto, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self._visibles = {s.clave for s in secciones_para(ctx)}
        self.tarjetas: list[widgets.TarjetaKPI] = []
        self.grafico_flota: widgets.GraficoDona | None = None
        self.grafico_tendencia: widgets.GraficoTendencia | None = None
        self.barras_categoria: list[QProgressBar] = []
        self.tabla_monitor: widgets.Tabla | None = None
        self.panel_alerta: QFrame | None = None
        self.boton_ver_analisis = None
        self.botones_acceso: dict = {}
        self.animaciones: list = []  # entradas, contadores y barras en curso
        self.ocupado = False

        exterior = QVBoxLayout(self)
        exterior.setContentsMargins(0, 0, 0, 0)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setFrameShape(QFrame.Shape.NoFrame)
        desplazable.viewport().setAutoFillBackground(False)
        exterior.addWidget(desplazable)
        lienzo = QWidget()
        lienzo.setObjectName("lienzoInicio")
        desplazable.setWidget(lienzo)
        self._capa = QVBoxLayout(lienzo)
        self._capa.setContentsMargins(0, 0, 10, 10)
        self._capa.setSpacing(16)

        cabecera = QVBoxLayout()
        cabecera.setSpacing(2)
        self.etiqueta_titulo = QLabel("Tablero de control")
        self.etiqueta_titulo.setObjectName("saludo")
        fila = QHBoxLayout()
        self.etiqueta_saludo = QLabel()
        self.etiqueta_saludo.setObjectName("subtituloVista")
        self.etiqueta_fecha = QLabel()
        self.etiqueta_fecha.setObjectName("subtituloVista")
        fila.addWidget(self.etiqueta_saludo)
        fila.addWidget(self.etiqueta_fecha)
        fila.addStretch(1)
        cabecera.addWidget(self.etiqueta_titulo)
        cabecera.addLayout(fila)
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
        self.etiqueta_fecha.setText("· Cargando…")
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
        self.etiqueta_fecha.setText("· " + datos["saludo"]["fecha"])
        nuevo = QWidget()
        capa = QVBoxLayout(nuevo)
        capa.setContentsMargins(6, 6, 6, 6)  # aire para que el brillo neón no se recorte
        capa.setSpacing(16)

        capa.addLayout(self._rejilla_kpi(datos))
        self.grafico_tendencia = self.grafico_flota = None
        self.barras_categoria, self.tabla_monitor = [], None
        self.panel_alerta = self.boton_ver_analisis = None
        self.botones_acceso = {}

        fila = QHBoxLayout()
        fila.setSpacing(16)
        if "tendencia" in datos:
            fila.addWidget(self._panel_tendencia(datos["tendencia"]), 3)
        if "flota" in datos:
            fila.addWidget(self._panel_flota(datos["flota"]), 2)
        if fila.count():
            capa.addLayout(fila)

        fila = QHBoxLayout()
        fila.setSpacing(16)
        if datos.get("flota", {}).get("por_categoria"):
            fila.addWidget(self._panel_categorias(datos["flota"]["por_categoria"]), 3)
        if "alerta_ia" in datos:
            fila.addWidget(self._panel_alerta(datos["alerta_ia"]), 2)
        if "mis_alquileres" in datos:
            fila.addWidget(self._panel_accesos(), 1)
        if fila.count():
            capa.addLayout(fila)

        if "eventos" in datos:
            capa.addWidget(self._panel_monitor(datos["eventos"]))

        self._capa.replaceWidget(self._contenido, nuevo)
        self._contenido.deleteLater()
        self._contenido = nuevo
        self._animar_entrada(nuevo)

    def _animar_entrada(self, contenido: QWidget):
        """Tarjetas y paneles entran en cascada; cifras cuentan y barras se llenan."""
        bloques = self.tarjetas + contenido.findChildren(widgets.Panel)
        animaciones = animacion.escalonar(bloques, paso=40)
        for tarjeta in self.tarjetas:
            animaciones.append(animacion.contar(tarjeta.etiqueta_valor, tarjeta.etiqueta_valor.text()))
        for barra in self.barras_categoria:
            animaciones.append(animacion.llenar(barra, barra.value()))
        self.animaciones = [a for a in animaciones if a is not None]

    # ---------------------------------------------------------------- bloques
    def _rejilla_kpi(self, datos: dict) -> QGridLayout:
        rejilla = QGridLayout()
        rejilla.setSpacing(16)
        self.tarjetas = []
        for i, d in enumerate(inicio.tarjetas_kpi(datos, self._visibles)):
            tarjeta = widgets.TarjetaKPI({**d, "icono": ICONO_KPI.get(d["clave"])})
            tarjeta.activada.connect(self.navegar)
            rejilla.addWidget(tarjeta, i // COLUMNAS, i % COLUMNAS)
            self.tarjetas.append(tarjeta)
        for columna in range(COLUMNAS):
            rejilla.setColumnStretch(columna, 1)
        return rejilla

    def _panel_tendencia(self, tendencia: dict) -> widgets.Panel:
        panel = _panel("Tendencia de alquileres", "Iniciados y devueltos · últimos 6 meses")
        self.grafico_tendencia = widgets.GraficoTendencia()
        self.grafico_tendencia.cargar(tendencia["meses"], [
            ("Iniciados", tendencia["iniciados"], "acento"),
            ("Devueltos", tendencia["devueltos"], "purpura_neon")])
        panel.capa.addWidget(self.grafico_tendencia, 1)
        return panel

    def _panel_flota(self, flota: dict) -> widgets.Panel:
        panel = _panel("Utilización de la flota", "Equipos alquilados o reservados")
        cuerpo = QHBoxLayout()
        self.grafico_flota = widgets.GraficoDona()
        self.grafico_flota.cargar(flota["conteos"], f"{flota['utilizacion']} %", "Utilización total")
        cuerpo.addWidget(self.grafico_flota, 1)
        leyenda = QVBoxLayout()
        leyenda.setSpacing(6)
        leyenda.addStretch(1)
        for estado, n in flota["conteos"]:
            fila = QLabel(f"<span style='color:{tema.COLOR_ESTADO[estado][0]}'>●</span>&nbsp; "
                          f"{estado} <b>{n}</b>")
            fila.setObjectName("kpiDetalle")
            leyenda.addWidget(fila)
        total = QLabel(f"Total de la flota: <b>{flota['total']}</b>")
        total.setObjectName("datoSistema")
        leyenda.addSpacing(6)
        leyenda.addWidget(total)
        leyenda.addStretch(1)
        cuerpo.addLayout(leyenda)
        panel.capa.addLayout(cuerpo, 1)
        return panel

    def _panel_categorias(self, categorias: list[dict]) -> widgets.Panel:
        panel = _panel("Ocupación por categoría", "Equipos alquilados sobre el total de cada categoría")
        for c in categorias:
            cabecera = QHBoxLayout()
            nombre = QLabel(c["categoria"].upper())
            nombre.setObjectName("tituloModulo")
            detalle = QLabel(f"{c['alquilados']} de {c['total']} · <b>{c['porcentaje']} %</b>")
            detalle.setObjectName("kpiDetalle")
            cabecera.addWidget(nombre)
            cabecera.addStretch(1)
            cabecera.addWidget(detalle)
            barra = QProgressBar()
            barra.setObjectName("barraNeon")
            barra.setRange(0, 100)
            barra.setValue(c["porcentaje"])
            barra.setTextVisible(False)
            panel.capa.addLayout(cabecera)
            panel.capa.addWidget(barra)
            self.barras_categoria.append(barra)
        panel.capa.addStretch(1)
        return panel

    def _panel_alerta(self, alerta: dict) -> widgets.Panel:
        panel = self.panel_alerta = _panel("Alertas de IA", "Mantenimiento preventivo")
        texto = QLabel(alerta["texto"])
        texto.setWordWrap(True)
        texto.setStyleSheet("font-weight: 600; font-size: 11pt;")
        panel.capa.addWidget(texto)
        insignias = QHBoxLayout()
        insignias.addWidget(widgets.Insignia("Estimación", "info"))
        if alerta["confianza"]:
            insignias.addWidget(widgets.Insignia(f"Confianza {nivel(alerta['confianza'])}",
                                                 widgets.tono_para(alerta["confianza"])))
        insignias.addStretch(1)
        panel.capa.addLayout(insignias)
        nota = QLabel("Puntaje por usos y días desde el último mantenimiento; "
                      "apoyo a la decisión, no una certeza.")
        nota.setObjectName("advertencia")
        nota.setWordWrap(True)
        panel.capa.addWidget(nota)
        if "analisis_ia" in self._visibles:
            self.boton_ver_analisis = widgets.boton(
                "Ver análisis", "primario", lambda: self.navegar.emit("analisis_ia"))
            panel.capa.addWidget(self.boton_ver_analisis, 0, Qt.AlignmentFlag.AlignLeft)
        panel.capa.addStretch(1)
        return panel

    def _panel_accesos(self) -> widgets.Panel:
        panel = _panel("Accesos rápidos")
        ayuda = QLabel("Consulte el catálogo de equipos disponibles o revise su historial "
                       "de alquileres y sus datos de contacto.")
        ayuda.setObjectName("subtituloVista")
        ayuda.setWordWrap(True)
        panel.capa.addWidget(ayuda)
        botones = QHBoxLayout()
        for clave, texto in (("equipos", "Ver equipos disponibles"), ("perfil", "Ir a Mi perfil")):
            if clave in self._visibles:
                b = widgets.boton(texto, "", lambda _=False, c=clave: self.navegar.emit(c))
                self.botones_acceso[clave] = b
                botones.addWidget(b)
        botones.addStretch(1)
        panel.capa.addLayout(botones)
        return panel

    def _panel_monitor(self, eventos: list[dict]) -> widgets.Panel:
        panel = _panel("Monitor de actividad", "Lo más urgente primero: vencidos, entregas de hoy, "
                                               "taller y reservas")
        if not eventos:
            vacio = QLabel("Sin actividad pendiente: no hay vencimientos, entregas ni equipos en taller.")
            vacio.setObjectName("subtituloVista")
            panel.capa.addWidget(vacio)
            return panel
        self.tabla_monitor = widgets.Tabla()
        self.tabla_monitor.setObjectName("monitor")
        self.tabla_monitor.cargar(COLUMNAS_MONITOR, eventos,
                                  colores={"estado": lambda texto: inicio.TONO_EVENTO.get(texto, "neutro")})
        cabecera = self.tabla_monitor.horizontalHeader()
        cabecera.setStretchLastSection(False)
        cabecera.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # el mensaje ocupa el espacio
        cabecera.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tabla_monitor.setColumnWidth(3, 120)
        self.tabla_monitor.setFixedHeight(46 + 31 * len(eventos))
        panel.capa.addWidget(self.tabla_monitor)
        return panel
