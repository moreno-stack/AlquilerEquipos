"""La migración Alembic debe producir exactamente el esquema de los modelos."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from alquiler.db import Base, crear_engine, init_db

TABLAS = {
    "usuario", "cliente", "categoria", "equipo", "alquiler",
    "devolucion", "pago", "mantenimiento", "recomendacion_ia",
}


def test_upgrade_crea_esquema(tmp_path):
    engine = crear_engine(tmp_path / "t.db")
    init_db(engine)
    tablas = set(inspect(engine).get_table_names())
    engine.dispose()
    assert TABLAS | {"alembic_version"} <= tablas


def test_migracion_coincide_con_modelos(tmp_path):
    # Si alguien cambia un modelo sin crear migración, esta prueba falla.
    engine = crear_engine(tmp_path / "t.db")
    init_db(engine)
    with engine.connect() as conn:
        diferencias = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diferencias == []


def test_init_db_es_idempotente(tmp_path):
    engine = crear_engine(tmp_path / "t.db")
    init_db(engine)
    init_db(engine)
    engine.dispose()
