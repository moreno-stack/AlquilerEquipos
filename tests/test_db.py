from sqlalchemy import text

from alquiler.db import crear_engine, crear_sessionmaker


def test_foreign_keys_activas():
    # SQLite las trae desactivadas por defecto: sin esto, las FK no protegen nada.
    engine = crear_engine("sqlite://")
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
    engine.dispose()


def test_crea_directorio_padre(tmp_path):
    # Primer arranque en Windows: la carpeta de datos aún no existe.
    ruta = tmp_path / "a" / "b" / "x.db"
    engine = crear_engine(ruta)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()
    assert ruta.exists()


def test_sessionmaker_no_expira_al_commit():
    engine = crear_engine("sqlite://")
    with crear_sessionmaker(engine)() as s:
        assert s.expire_on_commit is False
    engine.dispose()
