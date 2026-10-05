import socket

import pytest
from sqlalchemy.pool import StaticPool

import alquiler.models  # noqa: F401  (registra las tablas en Base.metadata)
from alquiler.db import Base, crear_engine, crear_sessionmaker


@pytest.fixture
def engine():
    engine = crear_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with crear_sessionmaker(engine)() as s:
        yield s


@pytest.fixture(autouse=True)
def sin_archivo_env(monkeypatch):
    """Ninguna prueba lee un alquiler.env real del disco (podría traer una clave de Groq)."""
    from alquiler import config
    monkeypatch.setattr(config, "_CARPETAS_ENV", ())


@pytest.fixture(autouse=True, scope="session")
def sin_red():
    """Aislamiento de red: ninguna prueba puede conectarse a internet (ni a la API de IA)."""
    def bloqueado(*args, **kwargs):
        raise RuntimeError("Prueba sin red: se intentó abrir una conexión de red.")

    originales = socket.socket.connect, socket.create_connection
    socket.socket.connect = bloqueado
    socket.create_connection = bloqueado
    yield
    socket.socket.connect, socket.create_connection = originales
