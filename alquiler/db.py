"""Conexión a SQLite y fábrica de sesiones."""

from pathlib import Path

from sqlalchemy import Engine, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Nombres de restricciones deterministas: Alembic los necesita para alterar
# tablas SQLite en modo batch.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def _activar_foreign_keys(dbapi_conn, _record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def crear_engine(url_o_ruta: str | Path, **kwargs) -> Engine:
    """Crea un engine SQLite con claves foráneas activas.

    Acepta una URL ``sqlite://...`` o una ruta de archivo; en el segundo caso
    crea los directorios padre si no existen.
    """
    if isinstance(url_o_ruta, str) and url_o_ruta.startswith("sqlite:"):
        url = url_o_ruta
    else:
        ruta = Path(url_o_ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{ruta}"
    engine = create_engine(url, **kwargs)
    event.listen(engine, "connect", _activar_foreign_keys)
    return engine


def crear_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Lleva el esquema de la base a la última migración (``alembic upgrade head``)."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
