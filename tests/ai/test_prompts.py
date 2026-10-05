"""Inyección de esquema y construcción de prompts (spec §6.4, paso 1 y 3)."""

from datetime import date

from alquiler.ai import prompts


def test_esquema_incluye_tablas_y_excluye_usuario():
    esquema = prompts.describir_esquema()
    for tabla in ("equipo", "alquiler", "pago", "cliente", "devolucion", "mantenimiento",
                  "categoria", "recomendacion_ia"):
        assert f"\n{tabla}(" in "\n" + esquema
    assert "'En mantenimiento'" in esquema and "'activo'" in esquema
    assert "usuario(" not in esquema and "password_hash" not in esquema
    assert "alembic_version" not in esquema


def test_esquema_refleja_fk_y_pk():
    esquema = prompts.describir_esquema()
    assert "cliente_id INTEGER FK→cliente.id" in esquema
    assert "id INTEGER PK" in esquema


def test_esquema_no_menciona_columna_fk_hacia_usuario():
    # registrado_por_id apunta a usuario: se expone el id, pero no la tabla vetada.
    assert "FK→usuario" not in prompts.describir_esquema()


def test_prompt_generacion_incluye_fecha_y_reglas():
    p = prompts.prompt_generacion(date(2026, 3, 10))
    assert "2026-03-10" in p
    assert "solo SELECT" in p
    assert "pesos" in p
    assert "aclaracion" in p and "no_resoluble" in p
    assert prompts.describir_esquema() in p


def test_esquemas_json_son_estrictos():
    for esquema in (prompts.ESQUEMA_GENERACION, prompts.ESQUEMA_RESPUESTA):
        assert esquema["additionalProperties"] is False
        assert set(esquema["required"]) == set(esquema["properties"])
    assert prompts.ESQUEMA_GENERACION["properties"]["tipo"]["enum"] == [
        "sql", "aclaracion", "no_resoluble"]


def test_mensaje_respuesta_limita_a_50_filas_y_avisa_truncado():
    filas = [(f"E-{i:03}", i) for i in range(200)]
    m = prompts.mensaje_respuesta("¿Cuáles?", "SELECT codigo, n FROM x", ["codigo", "n"], filas,
                                  truncado=True)
    assert "¿Cuáles?" in m and "SELECT codigo, n FROM x" in m
    assert "codigo | n" in m
    assert "E-049 | 49" in m and "E-050" not in m
    assert "50 de 200" in m and "truncado" in m


def test_mensaje_respuesta_formatea_none():
    m = prompts.mensaje_respuesta("p", "SELECT 1", ["a"], [(None,)], truncado=False)
    assert "(vacío)" in m
