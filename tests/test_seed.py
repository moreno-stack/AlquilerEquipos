"""Datos de demostración: representativos, deterministas y válidos según las reglas."""

from datetime import date

import pytest
from sqlalchemy import func, select
from sqlalchemy.pool import StaticPool

from alquiler import seed
from alquiler.ai.demanda import predecir_demanda
from alquiler.ai.mantenimiento import recomendar_mantenimiento
from alquiler.ai.retrasos import analizar_retrasos
from alquiler.auth import autenticar
from alquiler.db import Base, crear_engine, crear_sessionmaker
from alquiler.errors import ReglaNegocioError
from alquiler.models import (
    Alquiler,
    Cliente,
    Equipo,
    EstadoAlquiler,
    EstadoEquipo,
    Nivel,
    Rol,
    Usuario,
)
from alquiler.services import reportes

HOY = date(2026, 10, 4)


def _sesion_memoria():
    engine = crear_engine("sqlite://", connect_args={"check_same_thread": False},
                          poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine, crear_sessionmaker(engine)()


@pytest.fixture(scope="module")
def poblada():
    engine, s = _sesion_memoria()
    resumen = seed.poblar(s, HOY)
    yield s, resumen
    s.close()
    engine.dispose()


def _admin(s):
    return s.scalar(select(Usuario).where(Usuario.rol == Rol.ADMIN))


def test_resumen_y_volumen(poblada):
    s, r = poblada
    assert r["categorias"] >= 6 and r["equipos"] >= 35 and r["clientes"] >= 50
    assert r["alquileres"] >= 800
    assert r["alquileres"] == s.scalar(select(func.count()).select_from(Alquiler))


def test_estados_finales_variados(poblada):
    s, _ = poblada
    estados = set(s.scalars(select(Equipo.estado)))
    assert estados == set(EstadoEquipo)
    assert s.scalar(select(func.count()).where(Cliente.activo.is_(False))) >= 5
    activos = list(s.scalars(select(Alquiler).where(Alquiler.estado == EstadoAlquiler.ACTIVO)))
    assert len(activos) >= 3
    assert any(a.fecha_fin_prevista < HOY for a in activos)  # al menos uno en mora
    reservas = list(s.scalars(select(Alquiler).where(Alquiler.estado == EstadoAlquiler.RESERVADO)))
    assert any(r.fecha_inicio > HOY for r in reservas)                          # pendiente
    assert any(r.fecha_inicio <= HOY <= r.fecha_fin_prevista for r in reservas)  # lista
    assert any(r.fecha_fin_prevista < HOY for r in reservas)                    # vencida


def test_inactivos_no_tienen_alquileres_en_curso(poblada):
    s, _ = poblada
    for c in s.scalars(select(Cliente).where(Cliente.activo.is_(False))):
        assert all(a.estado not in (EstadoAlquiler.ACTIVO, EstadoAlquiler.RESERVADO)
                   for a in c.alquileres)


def test_usuarios_demo_autentican(poblada):
    s, _ = poblada
    assert autenticar(s, "admin", "admin1234").rol is Rol.ADMIN
    assert autenticar(s, "empleado", "empleado123").rol is Rol.EMPLEADO
    cliente = autenticar(s, "cliente", "cliente123")
    assert cliente.rol is Rol.CLIENTE and cliente.cliente.alquileres


def test_alimenta_a_los_analizadores(poblada):
    s, _ = poblada
    admin = _admin(s)
    alertas = recomendar_mantenimiento(s, admin, hoy=HOY, persistir=False)
    # Pocas y significativas: una demo con media flota en alerta no enseña nada.
    assert 1 <= len(alertas) <= s.scalar(select(func.count()).select_from(Equipo)) // 4
    assert analizar_retrasos(s, admin, persistir=False).clientes_marcados
    demanda = predecir_demanda(s, admin, hoy=HOY)
    assert any(r.confianza is Nivel.ALTA and "diciembre" in r.indicadores.get("picos", [])
               for r in demanda)
    assert reportes.ingresos(s, admin, date(2026, 1, 1), HOY).total > 0


def test_determinista():
    resumenes = []
    for _ in range(2):
        engine, s = _sesion_memoria()
        resumenes.append(seed.poblar(s, HOY, meses=4))
        s.close()
        engine.dispose()
    assert resumenes[0] == resumenes[1]


def test_no_puebla_dos_veces(poblada):
    s, _ = poblada
    with pytest.raises(ReglaNegocioError, match="vacía"):
        seed.poblar(s, HOY)


def test_cli_crea_base_y_puebla(tmp_path, monkeypatch, capsys):
    ruta = tmp_path / "Nueva carpeta" / "demo.db"
    monkeypatch.setenv("ALQUILER_DB_PATH", str(ruta))
    assert seed.main(["--hoy", "2026-10-04", "--meses", "3"]) == 0
    assert "alquileres" in capsys.readouterr().out
    engine = crear_engine(ruta)
    with crear_sessionmaker(engine)() as s:
        assert s.scalar(select(func.count()).select_from(Alquiler)) > 0
    engine.dispose()
    assert seed.main(["--hoy", "2026-10-04"]) == 1  # segunda vez: se niega sin romper
