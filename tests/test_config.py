from pathlib import Path

import pytest

from alquiler import config as modulo_config
from alquiler.config import buscar_archivo_env, cargar_config, leer_archivo_env


def test_valores_por_defecto():
    cfg = cargar_config({}, archivo=False)
    assert cfg.db_path == Path.home() / ".alquiler_equipos" / "alquiler.db"
    assert cfg.admin_password == "admin1234"
    assert cfg.factor_mora == 1.5
    assert cfg.groq_api_key is None
    assert cfg.origen_clave is None


def test_db_path_desde_entorno(tmp_path):
    cfg = cargar_config({"ALQUILER_DB_PATH": str(tmp_path / "x.db")}, archivo=False)
    assert cfg.db_path == tmp_path / "x.db"


def test_factor_mora_acepta_coma_decimal():
    # Configuración regional es-CO escribe los decimales con coma.
    assert cargar_config({"ALQUILER_FACTOR_MORA": "1,5"}, archivo=False).factor_mora == 1.5
    assert cargar_config({"ALQUILER_FACTOR_MORA": "2.25"}, archivo=False).factor_mora == 2.25


@pytest.mark.parametrize("valor", ["abc", "0", "-1"])
def test_factor_mora_invalido(valor):
    with pytest.raises(ValueError, match="ALQUILER_FACTOR_MORA"):
        cargar_config({"ALQUILER_FACTOR_MORA": valor}, archivo=False)


def test_api_key_vacia_es_none():
    assert cargar_config({"GROQ_API_KEY": "  "}, archivo=False).groq_api_key is None
    cfg = cargar_config({"GROQ_API_KEY": " gsk_x "}, archivo=False)
    assert (cfg.groq_api_key, cfg.origen_clave) == ("gsk_x", "entorno")


def test_valores_por_defecto_groq():
    cfg = cargar_config({}, archivo=False)
    assert cfg.groq_model == "openai/gpt-oss-20b"
    assert cfg.groq_timeout == 30.0
    assert cfg.groq_max_retries == 2


def test_variables_groq():
    cfg = cargar_config({"GROQ_MODEL": "openai/gpt-oss-120b", "GROQ_TIMEOUT": "12,5",
                         "GROQ_MAX_RETRIES": "0"}, archivo=False)
    assert (cfg.groq_model, cfg.groq_timeout, cfg.groq_max_retries) == (
        "openai/gpt-oss-120b", 12.5, 0)


@pytest.mark.parametrize("valor", ["0", "x", "-3"])
def test_timeout_invalido(valor):
    with pytest.raises(ValueError, match="GROQ_TIMEOUT"):
        cargar_config({"GROQ_TIMEOUT": valor}, archivo=False)


@pytest.mark.parametrize("valor", ["-1", "11", "dos", "1.5"])
def test_reintentos_fuera_de_rango(valor):
    with pytest.raises(ValueError, match="GROQ_MAX_RETRIES"):
        cargar_config({"GROQ_MAX_RETRIES": valor}, archivo=False)


# ---------------------------------------------------------------- alquiler.env
@pytest.fixture
def archivo_env(tmp_path):
    """Como lo deja el Bloc de notas de Windows: BOM, CRLF, comillas y espacios."""
    ruta = tmp_path / "alquiler.env"
    ruta.write_bytes(b'\xef\xbb\xbf# comentario\r\nGROQ_API_KEY = "gsk_abc123"\r\n\r\n'
                     b"OTRA=1\r\nlinea sin igual\r\nGROQ_MODEL='llama-3.3-70b-versatile'\r\n")
    return ruta


def test_archivo_env_formato(archivo_env):
    with pytest.warns(UserWarning, match="línea 5 ignorada"):
        datos = leer_archivo_env(archivo_env)
    assert datos == {"GROQ_API_KEY": "gsk_abc123", "GROQ_MODEL": "llama-3.3-70b-versatile"}


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_archivo_aporta_clave(archivo_env):
    cfg = cargar_config({}, archivo=archivo_env)
    assert (cfg.groq_api_key, cfg.origen_clave) == ("gsk_abc123", "archivo")
    assert cfg.groq_model == "llama-3.3-70b-versatile"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_entorno_gana_al_archivo(archivo_env):
    cfg = cargar_config({"GROQ_API_KEY": "gsk_env"}, archivo=archivo_env)
    assert (cfg.groq_api_key, cfg.origen_clave) == ("gsk_env", "entorno")


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_entorno_vacio_no_anula_archivo(archivo_env):
    cfg = cargar_config({"GROQ_API_KEY": "  "}, archivo=archivo_env)
    assert (cfg.groq_api_key, cfg.origen_clave) == ("gsk_abc123", "archivo")


def test_archivo_aporta_variables_alquiler(tmp_path):
    ruta = tmp_path / "alquiler.env"
    ruta.write_text("ALQUILER_FACTOR_MORA=2\nPATH=/malicioso\n", encoding="utf-8")
    assert leer_archivo_env(ruta) == {"ALQUILER_FACTOR_MORA": "2"}
    assert cargar_config({}, archivo=ruta).factor_mora == 2.0


def test_archivo_inexistente_se_ignora(tmp_path):
    assert cargar_config({}, archivo=tmp_path / "no.env").groq_api_key is None


def test_repr_enmascara_clave():
    cfg = cargar_config({"GROQ_API_KEY": "gsk_abc123"}, archivo=False)
    assert "gsk_abc123" not in repr(cfg)
    assert "…c123" in repr(cfg)


def test_buscar_archivo_env(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    b.mkdir()
    monkeypatch.setattr(modulo_config, "_CARPETAS_ENV", (a, b))
    assert buscar_archivo_env() is None
    (b / "alquiler.env").write_text("GROQ_API_KEY=x\n", encoding="utf-8")
    assert buscar_archivo_env() == b / "alquiler.env"
    a.mkdir()
    (a / "alquiler.env").write_text("GROQ_API_KEY=y\n", encoding="utf-8")
    assert buscar_archivo_env() == a / "alquiler.env"


def test_cargar_config_busca_el_archivo(tmp_path, monkeypatch):
    (tmp_path / "alquiler.env").write_text("GROQ_API_KEY=gsk_hallada\n", encoding="utf-8")
    monkeypatch.setattr(modulo_config, "_CARPETAS_ENV", (tmp_path,))
    assert cargar_config({}).groq_api_key == "gsk_hallada"


# ---------------------------------------------------------------- hallazgos de la revisión
def test_archivo_ansi_de_windows(tmp_path):
    """El Bloc de notas antiguo guarda en ANSI (cp1252): la tilde no debe impedir el arranque."""
    ruta = tmp_path / "alquiler.env"
    ruta.write_bytes("ALQUILER_ADMIN_PASSWORD=contraseña\r\nGROQ_API_KEY=gsk_x\r\n".encode("cp1252"))
    assert leer_archivo_env(ruta) == {"ALQUILER_ADMIN_PASSWORD": "contraseña", "GROQ_API_KEY": "gsk_x"}


def test_archivo_ilegible_se_ignora_con_aviso(tmp_path):
    carpeta = tmp_path / "alquiler.env"
    carpeta.mkdir()  # existe pero no se puede leer como archivo
    with pytest.warns(UserWarning, match="no se pudo leer"):
        assert leer_archivo_env(carpeta) == {}


def test_aviso_de_linea_invalida_no_muestra_la_clave(tmp_path):
    ruta = tmp_path / "alquiler.env"
    ruta.write_text("gsk_SECRETA123456\n", encoding="utf-8")
    with pytest.warns(UserWarning) as avisos:
        leer_archivo_env(ruta)
    assert "gsk_SECRETA123456" not in str(avisos[0].message)
    assert "línea 1" in str(avisos[0].message)


def test_comentario_al_final_de_la_linea(tmp_path):
    ruta = tmp_path / "alquiler.env"
    ruta.write_text('GROQ_API_KEY=gsk_abc  # mi clave\nGROQ_MODEL="modelo # con numeral"\n',
                    encoding="utf-8")
    assert leer_archivo_env(ruta) == {"GROQ_API_KEY": "gsk_abc", "GROQ_MODEL": "modelo # con numeral"}


def test_ruta_de_base_expande_la_carpeta_personal():
    cfg = cargar_config({"ALQUILER_DB_PATH": "~/datos/alq.db"}, archivo=False)
    assert cfg.db_path == Path.home() / "datos" / "alq.db"
