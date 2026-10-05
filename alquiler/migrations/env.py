"""Entorno de Alembic.

- Desde la app/pruebas: ``db.init_db`` pasa la conexión en ``config.attributes``.
- Desde la CLI (``alembic upgrade head``): usa ``ALQUILER_DB_PATH``.
"""

from alembic import context

import alquiler.models  # noqa: F401  (registra las tablas)
from alquiler.config import cargar_config
from alquiler.db import Base, crear_engine

target_metadata = Base.metadata


def _migrar(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite no soporta ALTER TABLE completo
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        _migrar(connection)
        return
    engine = crear_engine(cargar_config().db_path)
    with engine.connect() as conn:
        _migrar(conn)
    engine.dispose()


if context.is_offline_mode():
    raise SystemExit("El modo offline de Alembic no está soportado en este proyecto.")
run_migrations_online()
