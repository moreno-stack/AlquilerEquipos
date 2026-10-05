"""Raíz de composición: prepara la base, ofrece datos demo y arranca la interfaz.

Es el único módulo de ``alquiler.ui`` fuera de ``logica`` que toca el backend.
"""

import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QWidget
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from alquiler import __version__
from alquiler.ai.llm import crear_cliente
from alquiler.auth import asegurar_admin_inicial
from alquiler.config import Config, cargar_config
from alquiler.db import crear_engine, crear_sessionmaker, init_db
from alquiler.probar_ia import probar_ia
from alquiler.models import Equipo
from alquiler.ui.login import LoginDialog
from alquiler.ui.logica.contexto import Contexto
from alquiler.ui.ventana import VentanaPrincipal
from alquiler.ui.widgets import ESTILO, configurar_locale


def preparar_base(config: Config) -> sessionmaker[Session]:
    engine = crear_engine(config.db_path)
    init_db(engine)
    fabrica = crear_sessionmaker(engine)
    with fabrica() as sesion:
        asegurar_admin_inicial(sesion, config.admin_password)
    return fabrica


def base_vacia(fabrica: sessionmaker[Session]) -> bool:
    with fabrica() as sesion:
        return not sesion.scalar(select(func.count()).select_from(Equipo))


def ofrecer_demo(config: Config, fabrica: sessionmaker[Session], preguntar: Callable[[], bool],
                 cargar: Callable | None = None, hoy: Callable[[], date] = date.today) -> bool:
    """Si la base no tiene equipos, pregunta y carga los datos de demostración."""
    if not base_vacia(fabrica) or not preguntar():
        return False
    if cargar is None:
        from alquiler.seed import cargar_demo as cargar
    cargar(config.db_path, hoy(), config.admin_password)
    return True


def fabricas_de_vistas() -> dict[str, Callable[[Contexto], QWidget]]:
    """Vistas por clave de sección (se importan aquí para arrancar más rápido)."""
    from alquiler.ui.vistas.alquileres import VistaAlquileres
    from alquiler.ui.vistas.clientes import VistaClientes
    from alquiler.ui.vistas.consola_ia import VistaConsolaIA
    from alquiler.ui.vistas.equipos import VistaEquipos
    from alquiler.ui.vistas.ia import VistaAnalisisIA
    from alquiler.ui.vistas.inicio import VistaInicio
    from alquiler.ui.vistas.mantenimiento import VistaMantenimiento
    from alquiler.ui.vistas.perfil import VistaPerfil
    from alquiler.ui.vistas.reportes import VistaReportes
    from alquiler.ui.vistas.reservas import VistaReservas
    from alquiler.ui.vistas.usuarios import VistaUsuarios
    return {
        "inicio": VistaInicio, "equipos": VistaEquipos, "mantenimiento": VistaMantenimiento, "clientes": VistaClientes,
        "alquileres": VistaAlquileres, "reservas": VistaReservas, "reportes": VistaReportes,
        "usuarios": VistaUsuarios, "perfil": VistaPerfil, "analisis_ia": VistaAnalisisIA,
        "consola_ia": VistaConsolaIA,
    }


def _preguntar_demo() -> bool:
    respuesta = QMessageBox.question(
        None, "Base de datos vacía",
        "No hay equipos registrados. ¿Desea cargar datos de demostración "
        "(18 meses de historial simulado)?\n\nUsuarios: empleado/empleado123, cliente/cliente123.")
    return respuesta == QMessageBox.StandardButton.Yes


def autoprueba(config: Config, hoy: Callable[[], date] = date.today,
               fabricas: dict | None = None) -> int:
    """Verifica una instalación sin intervención: base, datos demo, login y las 11 secciones.

    Usa siempre una base temporal (con espacio y tilde en la ruta): nunca toca la base del
    usuario. Uso: ``python -m alquiler --autoprueba`` (también con el ejecutable empaquetado).
    """
    import dataclasses
    import shutil
    import tempfile
    from alquiler.ui import trabajador, widgets
    from alquiler.ui.logica.contexto import iniciar_sesion

    aplicacion = QApplication.instance() or QApplication(sys.argv[:1])
    errores: list[str] = []
    mostrar_error_original, gancho_original = widgets.mostrar_error, sys.excepthook
    widgets.mostrar_error = lambda parent, mensaje: errores.append(mensaje)
    sys.excepthook = lambda tipo, valor, tb: errores.append(f"{tipo.__name__}: {valor}")
    carpeta = Path(tempfile.mkdtemp(prefix="Autoprueba ñ "))
    config = dataclasses.replace(config, db_path=carpeta / "alquiler.db")
    try:
        fabrica = preparar_base(config)
        ofrecer_demo(config, fabrica, preguntar=lambda: True, hoy=hoy,
                     cargar=lambda ruta, dia, clave: _cargar_demo(ruta, dia, clave, meses=2))
        ctx = iniciar_sesion(fabrica, config, "admin", config.admin_password, reloj=hoy)
        ventana = VentanaPrincipal(ctx, fabricas or fabricas_de_vistas())
        for clave in ventana.claves_visibles():
            ventana.ir_a(clave)
            for _ in range(20):
                trabajador.esperar_tareas(250)
                aplicacion.processEvents()
        ventana.close()
        fabrica.kw["bind"].dispose()
        if errores:
            raise RuntimeError("; ".join(errores))
        print(f"AUTOPRUEBA OK: {len(ventana.claves_visibles())} secciones, base {config.db_path}")
        return 0
    except Exception as e:
        print(f"AUTOPRUEBA FALLÓ: {type(e).__name__}: {e}")
        return 1
    finally:
        widgets.mostrar_error, sys.excepthook = mostrar_error_original, gancho_original
        shutil.rmtree(carpeta, ignore_errors=True)


def _cargar_demo(*args, **kwargs):
    from alquiler.seed import cargar_demo
    return cargar_demo(*args, **kwargs)


def _hay_consola() -> bool:
    """El .exe de Windows es una aplicación de ventana: no tiene consola y ``sys.stdout`` es None."""
    return sys.stdout is not None


def _config_o_error() -> tuple[Config | None, str | None]:
    """Un valor inválido (p. ej. ``GROQ_TIMEOUT=30s`` en alquiler.env) se explica, no revienta."""
    try:
        return cargar_config(), None
    except ValueError as e:
        return None, (f"La configuración no es válida: {e}.\n\nRevise el archivo alquiler.env "
                      "(en la carpeta del programa) o las variables de entorno.")


def _probar_ia_con_dialogo(config: Config | None, error: str | None) -> int:
    """``--probar-ia`` sin consola: el resultado se muestra en un cuadro de diálogo."""
    lineas: list[str] = [error] if error else []
    codigo = 1 if error else probar_ia(config, imprimir=lineas.append)
    QApplication.instance() or QApplication(sys.argv[:1])
    mostrar = QMessageBox.information if codigo == 0 else QMessageBox.warning
    mostrar(None, "Prueba de la IA", "\n".join(lineas))
    return codigo


def main(argv: list[str] | None = None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    if "--version" in argumentos:
        print(f"Sistema Inteligente de Alquiler de Equipos {__version__}")
        return 0
    config, error = _config_o_error()
    if "--probar-ia" in argumentos:
        if not _hay_consola():
            return _probar_ia_con_dialogo(config, error)
        if error:
            print(error)
            return 1
        return probar_ia(config)
    if "--autoprueba" in argumentos:
        if error:
            print(f"AUTOPRUEBA FALLÓ: {error}")
            return 1
        return autoprueba(config)
    aplicacion = QApplication.instance() or QApplication(sys.argv[:1])
    if error:
        QMessageBox.critical(None, "Configuración no válida", error)
        return 1
    aplicacion.setStyleSheet(ESTILO)
    configurar_locale()
    fabrica = preparar_base(config)

    def cargar_con_aviso(*args):
        aviso = QLabel("Cargando datos de demostración…")
        aviso.setWindowFlag(Qt.WindowType.SplashScreen)
        aviso.setStyleSheet("padding: 24px; font-size: 14px; background: white;")
        aviso.show()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        aplicacion.processEvents()
        try:
            from alquiler.seed import cargar_demo
            cargar_demo(*args)
        finally:
            QApplication.restoreOverrideCursor()
            aviso.close()

    ofrecer_demo(config, fabrica, _preguntar_demo, cargar_con_aviso)
    cliente_llm = crear_cliente(config)
    while True:
        login = LoginDialog(fabrica, config, cliente_llm, date.today)
        if login.exec() != QDialog.DialogCode.Accepted:
            return 0
        ventana = VentanaPrincipal(login.contexto, fabricas_de_vistas())
        ventana.show()
        aplicacion.exec()
        if not ventana.cerro_sesion:
            return 0
