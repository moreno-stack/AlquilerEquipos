"""Comando --probar-ia: verifica la clave de Groq con una llamada real (aquí, simulada)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # el caso sin consola crea QApplication

import pytest  # noqa: E402

from alquiler.ai.llm import ErrorIA  # noqa: E402
from alquiler.config import cargar_config  # noqa: E402
from alquiler.probar_ia import probar_ia  # noqa: E402


class ClienteFalso:
    modelo = "openai/gpt-oss-20b"

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.esquemas = []

    def generar_json(self, sistema, mensajes, esquema):
        self.esquemas.append(esquema)
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


@pytest.fixture
def salida():
    lineas = []
    return lineas


def _config_con_archivo(tmp_path):
    ruta = tmp_path / "alquiler.env"
    ruta.write_text("GROQ_API_KEY=gsk_secreta_c123\n", encoding="utf-8")
    return cargar_config({}, archivo=ruta)


def test_sin_clave(salida):
    codigo = probar_ia(cargar_config({}, archivo=False), imprimir=salida.append)
    texto = "\n".join(salida)
    assert codigo == 2
    assert "GROQ_API_KEY" in texto and "alquiler.env.ejemplo" in texto


def test_ok(tmp_path, salida):
    falso = ClienteFalso({"ok": True})
    codigo = probar_ia(_config_con_archivo(tmp_path), crear=lambda cfg: falso,
                       imprimir=salida.append)
    texto = "\n".join(salida)
    assert codigo == 0
    assert "IA OK" in texto and "openai/gpt-oss-20b" in texto
    assert "…c123" in texto and "origen: archivo" in texto
    assert "gsk_secreta_c123" not in texto
    [esquema] = falso.esquemas
    assert esquema["required"] == ["ok"] and esquema["additionalProperties"] is False


def test_error_ia(tmp_path, salida):
    falso = ClienteFalso(ErrorIA("La clave de Groq no es válida o no tiene permisos."))
    codigo = probar_ia(_config_con_archivo(tmp_path), crear=lambda cfg: falso,
                       imprimir=salida.append)
    assert codigo == 1
    assert any("no es válida" in linea for linea in salida)


def test_respuesta_sin_ok(tmp_path, salida):
    codigo = probar_ia(_config_con_archivo(tmp_path), crear=lambda cfg: ClienteFalso({"ok": False}),
                       imprimir=salida.append)
    assert codigo == 1


def test_main_bandera(monkeypatch):
    from alquiler.ui import app
    monkeypatch.setattr(app, "probar_ia", lambda config: 7)
    monkeypatch.setattr(app, "QApplication", None)  # no debe abrir la interfaz
    assert app.main(["--probar-ia"]) == 7


def test_main_sin_consola_muestra_dialogo(monkeypatch, qapp):
    """En Windows el .exe no tiene consola (sys.stdout es None): el resultado va a un diálogo."""
    from alquiler.ui import app

    mostrados = []

    class DialogoFalso:
        @staticmethod
        def information(parent, titulo, texto):
            mostrados.append(("info", titulo, texto))

        @staticmethod
        def warning(parent, titulo, texto):
            mostrados.append(("aviso", titulo, texto))

    def probar_falso(config, imprimir=print):
        imprimir("La IA no está configurada: falta GROQ_API_KEY.")
        return 2

    monkeypatch.setattr(app, "_hay_consola", lambda: False)
    monkeypatch.setattr(app, "probar_ia", probar_falso)
    monkeypatch.setattr(app, "QMessageBox", DialogoFalso)
    assert app.main(["--probar-ia"]) == 2
    assert mostrados == [("aviso", "Prueba de la IA", "La IA no está configurada: falta GROQ_API_KEY.")]


def test_hay_consola(monkeypatch):
    import sys
    from alquiler.ui import app
    assert app._hay_consola() is True
    monkeypatch.setattr(sys, "stdout", None)
    resultado = app._hay_consola()
    monkeypatch.undo()
    assert resultado is False


def test_config_invalida_no_rompe_el_arranque(monkeypatch, capsys):
    """Un valor inválido en alquiler.env se explica; la app no muere con un traceback."""
    from alquiler.ui import app

    def config_rota():
        raise ValueError("GROQ_TIMEOUT debe ser un número de segundos, se recibió '30s'")

    monkeypatch.setattr(app, "cargar_config", config_rota)
    assert app.main(["--probar-ia"]) == 1
    salida = capsys.readouterr().out
    assert "GROQ_TIMEOUT" in salida and "alquiler.env" in salida
    assert app.main(["--autoprueba"]) == 1
    assert "GROQ_TIMEOUT" in capsys.readouterr().out


def test_config_invalida_en_la_interfaz_muestra_dialogo(monkeypatch, qapp):
    from alquiler.ui import app
    mostrados = []

    class DialogoFalso:
        @staticmethod
        def critical(parent, titulo, texto):
            mostrados.append((titulo, texto))

    def config_rota():
        raise ValueError("GROQ_MAX_RETRIES debe estar entre 0 y 10, se recibió '50'")

    monkeypatch.setattr(app, "cargar_config", config_rota)
    monkeypatch.setattr(app, "QMessageBox", DialogoFalso)
    assert app.main([]) == 1
    [(titulo, texto)] = mostrados
    assert "configuración" in titulo.lower() and "GROQ_MAX_RETRIES" in texto
