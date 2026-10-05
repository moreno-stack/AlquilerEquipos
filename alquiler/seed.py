"""Datos de demostración (spec §8): simulación determinista día por día.

Todo pasa por los servicios reales, así que los datos cumplen las mismas reglas de
negocio que la operación normal. Uso: ``python -m alquiler.seed [--hoy AAAA-MM-DD]``.
"""

import argparse
import math
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from alquiler import auth
from alquiler.config import cargar_config
from alquiler.db import crear_engine, crear_sessionmaker, init_db
from alquiler.errors import ReglaNegocioError
from alquiler.models import (
    Alquiler,
    Cliente,
    ConceptoPago,
    Devolucion,
    Equipo,
    EstadoEquipo,
    Mantenimiento,
    MetodoPago,
    Pago,
    Rol,
    TipoMantenimiento,
    Usuario,
)
from alquiler.services import alquileres, clientes, devoluciones, equipos, mantenimiento

FACTOR_MORA = 1.5
# nombre, prefijo, usos, días, n.º equipos, tarifa, alquileres/día, estacionalidad por mes
CATEGORIAS = [
    ("Taladros", "TAL", 20, 90, 8, 25_000, 0.50, {11: 1.3, 12: 2.2}),
    ("Andamios", "AND", 15, 120, 6, 40_000, 0.30, {6: 1.8, 7: 2.0, 12: 1.5}),
    ("Mezcladoras", "MEZ", 25, 90, 5, 55_000, 0.25, {1: 1.4, 2: 1.3, 12: 1.6}),
    ("Generadores", "GEN", 30, 60, 5, 70_000, 0.22, {4: 1.3, 12: 2.0}),
    ("Compresores", "COM", 25, 90, 5, 45_000, 0.20, {}),
    ("Herramienta eléctrica", "HER", 20, 90, 8, 20_000, 0.45, {12: 1.8}),
]
MODELOS = {
    "TAL": ["Taladro percutor", "Taladro inalámbrico", "Rotomartillo"],
    "AND": ["Andamio tubular", "Andamio certificado 2 m", "Andamio colgante"],
    "MEZ": ["Mezcladora 1 bulto", "Mezcladora 2 bultos"],
    "GEN": ["Generador 5 kW", "Generador 8 kW", "Generador diésel"],
    "COM": ["Compresor 50 L", "Compresor 100 L"],
    "HER": ["Pulidora", "Sierra circular", "Caladora", "Lijadora orbital"],
}
NOMBRES = ["Ana", "Luis", "Carlos", "María", "Jorge", "Paola", "Andrés", "Diana", "Felipe",
           "Laura", "Camilo", "Sandra", "Julián", "Natalia", "Óscar", "Valentina", "Mauricio",
           "Carolina", "Héctor", "Lorena"]
APELLIDOS = ["Pérez", "Gómez", "Rodríguez", "Martínez", "López", "Benavides", "Rosero",
             "Erazo", "Burbano", "Ortiz", "Delgado", "Muñoz", "Guerrero", "Cabrera", "Insuasty"]
DURACIONES = [1, 1, 2, 2, 3, 3, 4, 5, 7, 10, 14]
DANOS = ["Mandril golpeado", "Cable pelado", "Carcasa fisurada", "Rueda dañada",
         "Fuga de aceite", "Interruptor defectuoso"]
N_CLIENTES, N_MOROSOS, N_INACTIVOS = 60, 3, 5


def _poisson(rng: random.Random, media: float) -> int:
    limite, k, p = math.exp(-media), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limite:
            return k
        k += 1


def _usuario(session: Session, username: str, password: str, rol: Rol, nombre: str,
             cliente_id: int | None = None) -> Usuario:
    existente = session.scalar(select(Usuario).where(Usuario.username == username))
    return existente or auth.crear_usuario(session, username, password, rol, nombre, cliente_id)


def _contar(session: Session, modelo) -> int:
    return session.scalar(select(func.count()).select_from(modelo))


def poblar(session: Session, hoy: date, semilla: int = 42, meses: int = 18,
           admin_password: str = "admin1234") -> dict[str, int]:
    if _contar(session, Alquiler) or _contar(session, Equipo):
        raise ReglaNegocioError(
            "La base ya tiene datos; los datos de demostración solo se cargan en una base vacía.")
    rng = random.Random(semilla)
    admin = auth.asegurar_admin_inicial(session, admin_password) or session.scalar(
        select(Usuario).where(Usuario.rol == Rol.ADMIN))
    empleado = _usuario(session, "empleado", "empleado123", Rol.EMPLEADO, "Empleado Demo")
    inicio = hoy - timedelta(days=round(meses * 30.4))

    # ---- catálogo
    por_categoria: dict[int, tuple[float, dict]] = {}
    for nombre, pref, usos, dias, n, tarifa, tasa, estac in CATEGORIAS:
        cat = equipos.crear_categoria(session, admin, nombre, None, usos, dias)
        por_categoria[cat.id] = (tasa, estac)
        for i in range(1, n + 1):
            equipos.crear_equipo(
                session, admin, f"{pref}-{i:03}", rng.choice(MODELOS[pref]), cat.id,
                tarifa + rng.choice([-5_000, 0, 0, 5_000]),
                inicio - timedelta(days=rng.randint(30, 700)))

    # ---- clientes (los primeros N_MOROSOS suelen devolver tarde)
    propension: dict[int, float] = {}
    for i in range(N_CLIENTES):
        c = clientes.registrar_cliente(
            session, admin, f"1085{i:06d}", f"{NOMBRES[i % 20]} {APELLIDOS[(i * 7) % 15]}",
            f"31{rng.randint(10000000, 99999999)}",
            email=f"cliente{i}@correo.co" if rng.random() < 0.7 else None)
        propension[c.id] = 0.65 if i < N_MOROSOS else 0.07
    ids_clientes = sorted(propension)
    cliente_demo = ids_clientes[N_MOROSOS]  # puntual y con historial
    _usuario(session, "cliente", "cliente123", Rol.CLIENTE, "Cliente Demo", cliente_demo)

    devolver: dict[date, list[tuple[int, bool]]] = defaultdict(list)
    cerrar: dict[date, list[int]] = defaultdict(list)

    def disponibles(categoria_id=None):
        q = select(Equipo).where(Equipo.estado == EstadoEquipo.DISPONIBLE).order_by(Equipo.id)
        if categoria_id is not None:
            q = q.where(Equipo.categoria_id == categoria_id)
        return list(session.scalars(q))

    def pagar(alquiler_id, monto, concepto, dia):
        if monto > 0:
            alquileres.registrar_pago(session, empleado, alquiler_id, monto,
                                      rng.choice(list(MetodoPago)), concepto, hoy=dia)

    def alquilar(equipo_id, cliente_id, dia, duracion, devolucion=True):
        a = alquileres.crear_alquiler(session, empleado, cliente_id, equipo_id, dia,
                                      dia + timedelta(days=duracion), hoy=dia)
        r = rng.random()
        pagar(a.id, a.costo_estimado if r < 0.85 else a.costo_estimado // 2 if r < 0.95 else 0,
              ConceptoPago.ALQUILER, dia)
        if devolucion:
            retraso = rng.randint(1, 5) if rng.random() < propension[cliente_id] else 0
            devolver[a.fecha_fin_prevista + timedelta(days=retraso)].append(
                (a.id, rng.random() < 0.04))
        return a

    # ---- simulación día por día
    dia = inicio
    while dia <= hoy:
        for alquiler_id, con_danos in devolver.pop(dia, []):
            penalizacion = rng.choice([20_000, 40_000, 80_000]) if con_danos else 0
            d = devoluciones.registrar_devolucion(
                session, empleado, alquiler_id, dia, float(rng.randint(2, 9)), FACTOR_MORA,
                con_danos=con_danos, descripcion_danos=rng.choice(DANOS) if con_danos else None,
                penalizacion_danos=penalizacion)
            if d.recargo_mora and rng.random() < 0.7:
                pagar(alquiler_id, d.recargo_mora, ConceptoPago.MORA, dia)
            if con_danos:
                if rng.random() < 0.8:
                    pagar(alquiler_id, penalizacion, ConceptoPago.DANOS, dia)
                abierto = session.scalar(select(Mantenimiento.id).where(
                    Mantenimiento.equipo_id == d.alquiler.equipo_id,
                    Mantenimiento.fecha_fin.is_(None)))
                cerrar[dia + timedelta(days=rng.randint(2, 5))].append(abierto)
        for m_id in cerrar.pop(dia, []):
            mantenimiento.cerrar_mantenimiento(session, empleado, m_id,
                                               costo=rng.randint(3, 25) * 10_000, hoy=dia)
        for e in disponibles():
            # Preventivo por usos o por calendario; a veces se posterga (deja alertas reales).
            cerrados = [m for m in e.mantenimientos if m.fecha_fin is not None]
            ultimo = max(cerrados, key=lambda m: m.fecha_fin, default=None)
            usos = e.usos_acumulados - (ultimo.usos_al_momento if ultimo else 0)
            dias = (dia - (ultimo.fecha_fin if ultimo else e.fecha_adquisicion)).days
            vencido = (usos >= e.categoria.intervalo_mant_usos
                       or dias >= e.categoria.intervalo_mant_dias)
            if vencido and rng.random() < 0.10:
                m = mantenimiento.abrir_mantenimiento(session, empleado, e.id,
                                                      TipoMantenimiento.PREVENTIVO,
                                                      "Mantenimiento preventivo programado", hoy=dia)
                cerrar[dia + timedelta(days=rng.randint(1, 2))].append(m.id)
        for cat_id, (tasa, estac) in por_categoria.items():
            libres = disponibles(cat_id)
            for _ in range(_poisson(rng, tasa * estac.get(dia.month, 1.0))):
                if not libres:
                    break
                equipo = libres.pop(rng.randrange(len(libres)))
                alquilar(equipo.id, rng.choice(ids_clientes), dia, rng.choice(DURACIONES))
        dia += timedelta(days=1)

    # ---- estado final garantizado (spec §8)
    libres = disponibles()
    moroso = ids_clientes[0]
    alquilar(libres.pop(0).id, moroso, hoy - timedelta(days=6), 4, devolucion=False)  # en mora
    for creado, inicio_r, fin_r in ((hoy, 3, 6), (hoy - timedelta(days=2), -1, 2),
                                    (hoy - timedelta(days=9), -7, -4)):
        alquileres.crear_alquiler(session, empleado, rng.choice(ids_clientes[N_MOROSOS + 1:]),
                                  libres.pop(0).id, hoy + timedelta(days=inicio_r),
                                  hoy + timedelta(days=fin_r), hoy=creado)
    if not session.scalar(select(func.count()).where(Mantenimiento.fecha_fin.is_(None))):
        mantenimiento.abrir_mantenimiento(session, empleado, libres.pop(0).id,
                                          TipoMantenimiento.PREVENTIVO, "Revisión general", hoy=hoy)
    for _ in range(2):
        equipos.dar_de_baja(session, empleado, libres.pop().id)
    candidatos = [c for c in ids_clientes[N_MOROSOS + 1:]
                  if not clientes.alquileres_activos_cliente(session, admin, c)]
    for cliente_id in candidatos[-N_INACTIVOS:]:
        clientes.desactivar_cliente(session, admin, cliente_id)

    return {
        "categorias": len(CATEGORIAS),
        "equipos": _contar(session, Equipo),
        "clientes": _contar(session, Cliente),
        "alquileres": _contar(session, Alquiler),
        "devoluciones": _contar(session, Devolucion),
        "pagos": _contar(session, Pago),
        "mantenimientos": _contar(session, Mantenimiento),
        "usuarios": _contar(session, Usuario),
    }


def cargar_demo(db_path: Path, hoy: date, admin_password: str, semilla: int = 42,
                meses: int = 18) -> dict[str, int]:
    """Migra la base indicada y la puebla. Desactiva fsync durante la carga (miles de commits)."""
    engine = crear_engine(db_path)
    init_db(engine)
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA synchronous=OFF"))
    engine.dispose()  # las conexiones nuevas ya traen el PRAGMA
    try:
        with crear_sessionmaker(engine)() as session:
            return poblar(session, hoy, semilla, meses, admin_password)
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Carga los datos de demostración.")
    parser.add_argument("--hoy", type=date.fromisoformat, default=date.today())
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--meses", type=int, default=18)
    args = parser.parse_args(argv)
    config = cargar_config()
    try:
        resumen = cargar_demo(config.db_path, args.hoy, config.admin_password,
                              args.semilla, args.meses)
    except ReglaNegocioError as e:
        print(e, file=sys.stderr)
        return 1
    print(f"Datos de demostración cargados en {config.db_path}:")
    for clave, valor in resumen.items():
        print(f"  {clave}: {valor}")
    print("Usuarios: admin (contraseña configurada), empleado/empleado123, cliente/cliente123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
