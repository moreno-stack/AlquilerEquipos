"""La documentación no puede desincronizarse del código."""

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
INDICE = RAIZ / "PROJECT_INDEX.md"
RUTA = re.compile(r"`((?:alquiler|tests|docs|scripts)/[^`\s*]+)`")


def _rutas_citadas() -> set[str]:
    return set(RUTA.findall(INDICE.read_text(encoding="utf-8")))


def test_rutas_del_indice_existen():
    faltantes = sorted(r for r in _rutas_citadas() if not (RAIZ / r).exists())
    assert faltantes == []


def test_todo_modulo_esta_indexado():
    citadas = _rutas_citadas()
    modulos = sorted(str(p.relative_to(RAIZ)).replace("\\", "/")
                     for p in (RAIZ / "alquiler").rglob("*.py") if "__pycache__" not in p.parts)
    assert [m for m in modulos if m not in citadas] == []


def test_toda_prueba_esta_indexada():
    citadas = _rutas_citadas()
    pruebas = sorted(str(p.relative_to(RAIZ)).replace("\\", "/")
                     for p in (RAIZ / "tests").rglob("test_*.py"))
    assert [p for p in pruebas if p not in citadas] == []


def test_readme_documenta_groq():
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    for texto in ("GROQ_API_KEY", "alquiler.env", "--probar-ia", "openai/gpt-oss-20b",
                  "console.groq.com/keys", "Inicio"):
        assert texto in readme, texto
    assert "ANTHROPIC" not in readme and "Anthropic" not in readme


def test_readme_documenta_todas_las_variables():
    import re
    from alquiler import config
    fuente = Path(config.__file__).read_text(encoding="utf-8")
    variables = set(re.findall(r'"((?:GROQ|ALQUILER)_[A-Z_]+)"', fuente))
    readme = (RAIZ / "README.md").read_text(encoding="utf-8")
    assert variables and all(f"`{v}`" in readme for v in variables), variables


def test_empaquetado_incluye_plantilla_env():
    spec = (RAIZ / "AlquilerEquipos.spec").read_text(encoding="utf-8")
    assert "alquiler.env.ejemplo" in spec
