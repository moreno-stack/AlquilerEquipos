"""tokens.css es la única fuente de verdad: la app de escritorio lee sus colores de ahí."""

import re
from pathlib import Path

import pytest

from alquiler.ui import tema

RAIZ = Path(__file__).resolve().parents[2]


def test_la_app_lee_el_archivo_del_sistema_de_diseno():
    assert tema.RUTA_TOKENS == RAIZ / "diseno" / "tokens.css"
    assert (RAIZ / "diseno" / "DESIGN.md").is_file()


def test_paleta_sale_de_tokens_css():
    tokens = tema.leer_tokens(tema.RUTA_TOKENS)
    for clave, variable in tema.MAPA_PALETA.items():
        assert tema.PALETA[clave] == tokens[variable].upper(), clave
    assert tema.COLOR_ESTADO["En mantenimiento"] == (
        tokens["--estado-mantenimiento-fuerte"], tokens["--estado-mantenimiento-fondo"],
        tokens["--estado-mantenimiento-texto"])


def test_tema_py_no_escribe_colores():
    fuente = Path(tema.__file__).read_text(encoding="utf-8")
    assert not re.search(r"#[0-9A-Fa-f]{6}\b", fuente)


def test_lector_ignora_comentarios_y_toma_la_primera_definicion(tmp_path):
    css = tmp_path / "t.css"
    css.write_text("/* --falso: #000000; */\n:root {\n  --color-a: #ABCDEF; /* nota */\n"
                   "  --duracion: 200ms;\n}\n@media (prefers-reduced-motion: reduce) {\n"
                   "  :root { --duracion: 0ms; }\n}\n", encoding="utf-8")
    assert tema.leer_tokens(css) == {"--color-a": "#ABCDEF", "--duracion": "200ms"}


def test_token_faltante_da_un_error_claro(tmp_path):
    css = tmp_path / "t.css"
    css.write_text(":root { --color-fondo: #000000; }", encoding="utf-8")
    with pytest.raises(KeyError, match="--color-superficie"):
        tema.construir_paleta(tema.leer_tokens(css))


def test_ejecutable_empaqueta_los_tokens():
    assert "tokens.css" in (RAIZ / "AlquilerEquipos.spec").read_text(encoding="utf-8")


def test_styleguide_solo_usa_variables():
    """La página de componentes no escribe colores: todos salen de tokens.css."""
    html = (RAIZ / "diseno" / "styleguide.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="tokens.css">' in html
    sin_enlaces = re.sub(r'(href|id)="#?[\w-]+"', "", html)  # anclas como #colores no son colores
    assert not re.search(r"#[0-9A-Fa-f]{3,8}(?![\w-])", sin_enlaces)
    assert not re.search(r"\brgba?\(|\bhsla?\(|(?<![\w-])(white|black)(?![\w-])", html)


def test_styleguide_usa_variables_que_existen():
    html = (RAIZ / "diseno" / "styleguide.html").read_text(encoding="utf-8")
    usadas = set(re.findall(r"var\((--[\w-]+)\)", html)) | set(re.findall(r'"(--[\w-]+)"', html))
    definidas = set(tema.leer_tokens(tema.RUTA_TOKENS))
    assert usadas - definidas == set()
