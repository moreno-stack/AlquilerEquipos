"""Validador estático y ejecutor de solo lectura para el SQL generado por la IA."""

from datetime import date

import pytest
from sqlalchemy import text

from alquiler.ai import sql_seguro as sq
from alquiler.db import crear_engine, init_db


# ---------------------------------------------------------------- validador estático
@pytest.mark.parametrize("sql,esperado", [
    ("  SELECT codigo FROM equipo ;  ", "SELECT codigo FROM equipo"),
    ("WITH t AS (SELECT 1 AS x) SELECT x FROM t", "WITH t AS (SELECT 1 AS x) SELECT x FROM t"),
    ("SELECT replace(nombre, 'a', 'b') FROM equipo", None),
    ("SELECT * FROM equipo WHERE descripcion LIKE '%drop table%' -- delete", None),
    ("select * from equipo /* update */ where estado = 'Disponible'", None),
    ('SELECT "nombre" FROM cliente WHERE nombre = \'O\'\'Brien; DELETE\'', None),
])
def test_permite(sql, esperado):
    assert sq.validar_sql(sql) == (esperado or sql.strip().rstrip(";").strip())


@pytest.mark.parametrize("sql", [
    "INSERT INTO pago VALUES (1)",
    "UPDATE equipo SET tarifa_diaria = 1",
    "DELETE FROM pago",
    "DROP TABLE pago",
    "ALTER TABLE equipo ADD COLUMN x",
    "CREATE TABLE x (a)",
    "REPLACE INTO pago VALUES (1)",
    "ATTACH DATABASE 'x.db' AS x",
    "PRAGMA writable_schema = 1",
    "VACUUM",
    "WITH x AS (SELECT 1) DELETE FROM pago",
    "SELECT 1; DROP TABLE pago",
    "SELECT * FROM usuario",
    "SELECT password_hash FROM cliente",
    "SELECT load_extension('x')",
    "EXPLAIN SELECT 1",
    "",
    "   ;  ",
])
def test_rechaza(sql):
    with pytest.raises(sq.ErrorSQL):
        sq.validar_sql(sql)


def test_motivo_legible():
    with pytest.raises(sq.ErrorSQL, match="DELETE"):
        sq.validar_sql("WITH x AS (SELECT 1) DELETE FROM pago")
    with pytest.raises(sq.ErrorSQL, match="una sola sentencia"):
        sq.validar_sql("SELECT 1; SELECT 2")


# ---------------------------------------------------------------- ejecutor
@pytest.fixture
def db(tmp_path):
    """Base real en una ruta con espacio y tilde, como la carpeta del usuario."""
    ruta = tmp_path / "Nueva carpeta ñ" / "alquiler.db"
    engine = crear_engine(ruta)
    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO categoria (nombre, intervalo_mant_usos, intervalo_mant_dias)"
                          " VALUES ('Taladros', 20, 90)"))
        for i in range(250):
            conn.execute(text(
                "INSERT INTO equipo (codigo, nombre, categoria_id, estado, tarifa_diaria, "
                "usos_acumulados, horas_uso_acumuladas, fecha_adquisicion) VALUES "
                f"('E-{i:03}', 'Equipo {i}', 1, 'Disponible', 1000, 0, 0, '{date(2025, 1, 1)}')"))
        conn.execute(text("INSERT INTO usuario (username, password_hash, nombre_completo, rol, "
                          "activo, creado_en) VALUES ('admin', 'secreto', 'A', 'administrador', 1, "
                          "'2026-01-01 00:00:00')"))
    engine.dispose()
    return ruta


def test_ejecuta_y_devuelve_columnas(db):
    r = sq.ejecutar_lectura(db, "SELECT codigo, tarifa_diaria FROM equipo ORDER BY codigo LIMIT 2")
    assert r.columnas == ["codigo", "tarifa_diaria"]
    assert r.filas == [("E-000", 1000), ("E-001", 1000)]
    assert r.truncado is False and r.milisegundos >= 0


def test_trunca_a_limite(db):
    r = sq.ejecutar_lectura(db, "SELECT codigo FROM equipo")
    assert len(r.filas) == 200 and r.truncado is True


def test_ejecutar_valida_antes_de_tocar_la_base(db):
    with pytest.raises(sq.ErrorSQL):
        sq.ejecutar_lectura(db, "DELETE FROM equipo")
    assert len(sq.ejecutar_lectura(db, "SELECT id FROM equipo", limite=1000).filas) == 250


def test_autorizador_bloquea_usuario_aunque_se_evada_el_validador(db):
    with pytest.raises(sq.ErrorSQL, match="no permitido"):
        sq._ejecutar_sin_validar(db, 'SELECT * FROM "usuario"', 200, 3.0)


def test_conexion_es_de_solo_lectura(db):
    with pytest.raises(sq.ErrorSQL):
        sq._ejecutar_sin_validar(db, "DELETE FROM equipo", 200, 3.0)
    assert len(sq.ejecutar_lectura(db, "SELECT id FROM equipo", limite=1000).filas) == 250


def test_timeout(db):
    infinito = ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) "
                "SELECT count(*) FROM n")
    with pytest.raises(sq.ErrorSQL, match="tardó demasiado"):
        sq.ejecutar_lectura(db, infinito, timeout_s=0.2)


@pytest.mark.parametrize("sql", ["SELECT columna_inexistente FROM equipo", "SELECT FROM WHERE"])
def test_sql_con_error_de_sintaxis_o_columna(db, sql):
    with pytest.raises(sq.ErrorSQL, match="SQLite"):
        sq.ejecutar_lectura(db, sql)


def test_base_inexistente(tmp_path):
    with pytest.raises(sq.ErrorSQL):
        sq.ejecutar_lectura(tmp_path / "no_existe.db", "SELECT 1")


@pytest.mark.parametrize("sql", ["SELECT sql FROM sqlite_master WHERE name = 'usuario'",
                                 "SELECT * FROM sqlite_schema"])
def test_esquema_interno_vetado_en_ambas_barreras(db, sql):
    # El esquema de "usuario" (con password_hash) no debe llegar al modelo.
    with pytest.raises(sq.ErrorSQL):
        sq.validar_sql(sql)
    with pytest.raises(sq.ErrorSQL):
        sq._ejecutar_sin_validar(db, sql, 200, 3.0)


def test_blob_gigante_se_rechaza(db):
    # Una sola reserva enorme no la frena el timeout: podría congelar el escritorio.
    with pytest.raises(sq.ErrorSQL, match="demasiado grande"):
        sq.ejecutar_lectura(db, "SELECT length(randomblob(5000000))")
