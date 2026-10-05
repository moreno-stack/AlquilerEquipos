"""Fixtures de la interfaz: base en archivo, contextos por rol y un modelo de IA falso."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date  # noqa: E402

import pytest  # noqa: E402

from alquiler.config import cargar_config  # noqa: E402
from alquiler.db import crear_engine, crear_sessionmaker, init_db  # noqa: E402
from alquiler.models import Categoria, Cliente, Equipo, Rol, Usuario  # noqa: E402
from alquiler.ui.logica.contexto import Contexto, UsuarioSesion  # noqa: E402

HOY = date(2026, 3, 10)


class ClienteFalso:
    """Sustituye al cliente de Groq: devuelve respuestas guionadas y registra las llamadas."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def generar_json(self, sistema, mensajes, esquema):
        self.llamadas.append({"sistema": sistema, "mensajes": list(mensajes), "esquema": esquema})
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def config(tmp_path):
    return cargar_config({"ALQUILER_DB_PATH": str(tmp_path / "ui.db")})


@pytest.fixture
def fabrica(config):
    engine = crear_engine(config.db_path)
    init_db(engine)
    yield crear_sessionmaker(engine)
    engine.dispose()


@pytest.fixture
def datos_base(fabrica):
    """Una categoría, dos equipos disponibles y un cliente activo."""
    with fabrica() as s:
        cat = Categoria(nombre="Taladros")
        s.add_all([
            Equipo(codigo="TAL-001", nombre="Taladro percutor", categoria=cat,
                   tarifa_diaria=25_000, fecha_adquisicion=date(2025, 1, 10)),
            Equipo(codigo="TAL-002", nombre="Taladro inalámbrico", categoria=cat,
                   tarifa_diaria=30_000, fecha_adquisicion=date(2025, 2, 1)),
            Cliente(documento="1085000001", nombre="Ana Pérez", telefono="3001234567"),
        ])
        s.commit()


@pytest.fixture
def ctx_factory(fabrica, config):
    """ctx_factory("admin" | "empleado" | "cliente", cliente_llm=None) -> Contexto."""

    def hacer(rol="admin", cliente_llm=None, username=None):
        rol_enum = {"admin": Rol.ADMIN, "empleado": Rol.EMPLEADO, "cliente": Rol.CLIENTE}[rol]
        username = username or rol
        with fabrica() as s:
            u = s.query(Usuario).filter_by(username=username).one_or_none()
            if u is None:
                cliente = None
                if rol_enum is Rol.CLIENTE:
                    cliente = s.query(Cliente).first() or Cliente(
                        documento="999", nombre="Cliente Demo", telefono="300")
                u = Usuario(username=username, password_hash="x", nombre_completo=username.title(),
                            rol=rol_enum, cliente=cliente)
                s.add(u)
                s.commit()
            sesion = UsuarioSesion.desde(u)
        return Contexto(fabrica, sesion, config, cliente_llm=cliente_llm, reloj=lambda: HOY)

    return hacer
