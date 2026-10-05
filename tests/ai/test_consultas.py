"""Orquestador Text-to-SQL con explicabilidad (spec §6.4). El modelo es un falso."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from alquiler.ai import consultas as cq
from alquiler.ai.llm import ErrorIA
from alquiler.db import crear_engine, crear_sessionmaker, init_db
from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.models import (
    Alquiler,
    Categoria,
    Cliente,
    ConceptoPago,
    Devolucion,
    Equipo,
    EstadoAlquiler,
    MetodoPago,
    Pago,
    Rol,
    Usuario,
)

HOY = date(2026, 3, 10)
SQL_TOP = ("SELECT e.codigo, COUNT(*) AS alquileres FROM alquiler a JOIN equipo e "
           "ON e.id = a.equipo_id GROUP BY e.id ORDER BY alquileres DESC")
PASOS = ["Uso la tabla alquiler unida a equipo.", "Cuento alquileres por equipo y ordeno."]


class ClienteFalso:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def generar_json(self, sistema, mensajes, esquema):
        self.llamadas.append({"sistema": sistema, "mensajes": list(mensajes), "esquema": esquema})
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def gen(sql=SQL_TOP, tipo="sql", pasos=PASOS, mensaje="", sugerencias=()):
    return {"tipo": tipo, "sql": sql, "pasos": list(pasos), "mensaje": mensaje,
            "sugerencias": list(sugerencias)}


@pytest.fixture
def db(tmp_path):
    ruta = tmp_path / "Nueva carpeta" / "alquiler.db"
    engine = crear_engine(ruta)
    init_db(engine)
    s = crear_sessionmaker(engine)()
    cat = Categoria(nombre="Taladros")
    e1 = Equipo(codigo="TAL-001", nombre="Taladro", categoria=cat, tarifa_diaria=25_000,
                fecha_adquisicion=date(2025, 1, 1))
    e2 = Equipo(codigo="TAL-002", nombre="Taladro 2", categoria=cat, tarifa_diaria=30_000,
                fecha_adquisicion=date(2025, 1, 1))
    cli = Cliente(documento="1", nombre="Ana Pérez", telefono="3")
    s.add_all([e1, e2, cli,
               Usuario(username="admin", password_hash="x", nombre_completo="A", rol=Rol.ADMIN),
               Usuario(username="emp", password_hash="x", nombre_completo="E", rol=Rol.EMPLEADO)])
    for equipo, inicio in ((e1, date(2026, 3, 1)), (e1, date(2026, 3, 5)), (e2, date(2026, 3, 2))):
        a = Alquiler(cliente=cli, equipo=equipo, fecha_inicio=inicio,
                     fecha_fin_prevista=inicio + timedelta(days=2), tarifa_diaria=1,
                     costo_estimado=2, estado=EstadoAlquiler.FINALIZADO)
        s.add_all([a, Devolucion(alquiler=a, fecha_devolucion=inicio + timedelta(days=3),
                                 dias_retraso=1, recargo_mora=0, horas_uso=1, total=2),
                   Pago(alquiler=a, monto=2, fecha=inicio, metodo=MetodoPago.EFECTIVO,
                        concepto=ConceptoPago.ALQUILER)])
    s.commit()
    yield s, ruta
    s.close()
    engine.dispose()


def _actor(s, username="admin"):
    return s.scalar(select(Usuario).where(Usuario.username == username))


def _consultar(db, cliente, pregunta="¿Qué equipos se alquilan más?"):
    s, ruta = db
    return cq.consultar(s, _actor(s), pregunta, cliente, ruta, hoy=HOY)


# ---------------------------------------------------------------- entrada
@pytest.mark.parametrize("pregunta", ["", "   ", "x" * 501])
def test_pregunta_vacia_o_larga_no_llama_api(db, pregunta):
    falso = ClienteFalso()
    with pytest.raises(ReglaNegocioError):
        _consultar(db, falso, pregunta)
    assert falso.llamadas == []


def test_empleado_sin_permiso(db):
    s, ruta = db
    with pytest.raises(PermisoDenegado):
        cq.consultar(s, _actor(s, "emp"), "¿Algo?", ClienteFalso(), ruta, hoy=HOY)


def test_sin_api_ofrece_predefinidas(db):
    r = _consultar(db, None)
    assert r.estado == "sin_api"
    assert r.sugerencias == [c.titulo for c in cq.CONSULTAS_PREDEFINIDAS] and len(r.sugerencias) == 6
    assert "GROQ_API_KEY" in r.respuesta and "alquiler.env" in r.respuesta


# ---------------------------------------------------------------- flujo principal
def test_flujo_ok_dos_partes(db):
    falso = ClienteFalso(gen(), {"respuesta": "El TAL-001 es el más alquilado (2 veces)."})
    r = _consultar(db, falso)
    assert r.estado == "ok"
    assert r.respuesta == "El TAL-001 es el más alquilado (2 veces)."  # parte 1: respuesta directa
    assert r.pasos == PASOS                                               # parte 2: explicación
    assert r.sql == SQL_TOP and r.columnas == ["codigo", "alquileres"]
    assert r.filas == [("TAL-001", 2), ("TAL-002", 1)]                   # datos reales de la base
    assert r.advertencia == cq.ADVERTENCIA
    assert len(falso.llamadas) == 2
    segunda = falso.llamadas[1]["mensajes"][0]["content"]
    assert "¿Qué equipos se alquilan más?" in segunda and SQL_TOP in segunda
    assert "TAL-001 | 2" in segunda
    assert "2026-03-10" in falso.llamadas[0]["sistema"]


def test_sin_datos_no_hace_segunda_llamada(db):
    falso = ClienteFalso(gen("SELECT codigo FROM equipo WHERE estado = 'Fuera de servicio'"))
    r = _consultar(db, falso)
    assert r.estado == "sin_datos"
    assert "no devolvió registros" in r.respuesta
    assert r.pasos == PASOS and r.filas == [] and r.sugerencias
    assert len(falso.llamadas) == 1


def test_aclaracion(db):
    falso = ClienteFalso(gen(tipo="aclaracion", sql="", pasos=[],
                             mensaje="¿De qué período?", sugerencias=["Ingresos de marzo"]))
    r = _consultar(db, falso, "¿Cuánto ganamos?")
    assert (r.estado, r.respuesta, r.sugerencias, r.sql) == (
        "aclaracion", "¿De qué período?", ["Ingresos de marzo"], None)


def test_no_resoluble(db):
    falso = ClienteFalso(gen(tipo="no_resoluble", sql="", pasos=[],
                             mensaje="No se registra el clima.", sugerencias=["Alquileres por mes"]))
    r = _consultar(db, falso, "¿Llovió en marzo?")
    assert (r.estado, r.respuesta) == ("no_resoluble", "No se registra el clima.")


# ---------------------------------------------------------------- seguridad y corrección
def _pagos(db):
    return db[0].scalar(select(func.count()).select_from(Pago))


def test_sql_destructivo_se_rechaza_y_se_corrige(db):
    falso = ClienteFalso(gen("DELETE FROM pago"), gen(), {"respuesta": "Listo."})
    r = _consultar(db, falso)
    assert r.estado == "ok" and r.sql == SQL_TOP
    assert _pagos(db) == 3
    correccion = falso.llamadas[1]["mensajes"][-1]["content"]
    assert "DELETE" in correccion


def test_dos_fallos_dan_error_con_sql_visible(db):
    falso = ClienteFalso(gen("DROP TABLE pago"), gen("SELECT * FROM usuario"))
    r = _consultar(db, falso)
    assert r.estado == "error" and r.sql == "SELECT * FROM usuario"
    assert "no fue posible" in r.respuesta.lower()
    assert _pagos(db) == 3 and len(falso.llamadas) == 2


def test_sql_que_falla_al_ejecutar_tambien_se_corrige(db):
    falso = ClienteFalso(gen("SELECT columna_rara FROM equipo"), gen(), {"respuesta": "Ok."})
    assert _consultar(db, falso).estado == "ok"
    assert "SQLite" in falso.llamadas[1]["mensajes"][-1]["content"]


# ---------------------------------------------------------------- errores del modelo
def test_error_ia_da_estado_error(db):
    r = _consultar(db, ClienteFalso(ErrorIA("Sin conexión con el servicio de IA.")))
    assert (r.estado, r.respuesta) == ("error", "Sin conexión con el servicio de IA.")


@pytest.mark.parametrize("raw", [
    {"sql": SQL_TOP},                                   # falta "tipo"
    {**gen(), "tipo": "otra_cosa"},
    {**gen(), "pasos": "no es lista"},
    {**gen(), "sql": ""},                               # tipo sql sin consulta
])
def test_respuesta_con_forma_invalida(db, raw):
    r = _consultar(db, ClienteFalso(raw))
    assert r.estado == "error" and "formato inesperado" in r.respuesta


def test_segunda_llamada_sin_respuesta_valida(db):
    r = _consultar(db, ClienteFalso(gen(), {"otra": 1}))
    assert r.estado == "error"


def test_truncado_se_advierte_y_solo_50_filas_al_modelo(db):
    sql = ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 300) "
           "SELECT x FROM n")
    falso = ClienteFalso(gen(sql), {"respuesta": "Muchos."})
    r = _consultar(db, falso)
    assert r.truncado and len(r.filas) == 200
    assert "truncad" in r.advertencia.lower()
    tabla = falso.llamadas[1]["mensajes"][0]["content"]
    assert "\n50\n" in tabla + "\n" and "\n51\n" not in tabla + "\n"


# ---------------------------------------------------------------- predefinidas
@pytest.mark.parametrize("consulta", [c for c in cq.CONSULTAS_PREDEFINIDAS if c.sql])
def test_todas_las_predefinidas_pasan_el_validador(consulta):
    from alquiler.ai.sql_seguro import validar_sql
    validar_sql(cq.sql_predefinida(consulta, HOY))


@pytest.mark.parametrize("id_", [c.id for c in cq.CONSULTAS_PREDEFINIDAS])
def test_predefinidas_ejecutan_sobre_base_real(db, id_):
    s, ruta = db
    r = cq.ejecutar_predefinida(s, _actor(s), id_, ruta, hoy=HOY)
    assert r.estado in ("ok", "sin_datos") and r.pasos and r.columnas


def test_predefinida_top_equipos_mes(db):
    s, ruta = db
    r = cq.ejecutar_predefinida(s, _actor(s), "top_equipos_mes", ruta, hoy=HOY)
    assert r.filas[0][:2] == ("TAL-001", "Taladro") and r.respuesta == "2 registros."


def test_equipos_a_revisar_usa_recomendador(db):
    s, ruta = db
    s.scalar(select(Equipo).where(Equipo.codigo == "TAL-001")).usos_acumulados = 60
    s.commit()
    r = cq.ejecutar_predefinida(s, _actor(s), "equipos_a_revisar", ruta, hoy=HOY)
    assert r.columnas[0] == "codigo" and r.filas[0][0] == "TAL-001"
    assert "Estimación" in r.advertencia


def test_predefinida_inexistente(db):
    s, ruta = db
    with pytest.raises(ReglaNegocioError):
        cq.ejecutar_predefinida(s, _actor(s), "nada", ruta, hoy=HOY)
