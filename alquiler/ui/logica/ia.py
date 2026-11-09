"""Lógica de presentación del módulo de IA: tarjetas explicables y consola."""

import dataclasses

from alquiler import config as configuracion
from alquiler.ai import consultas
from alquiler.ai.llm import crear_cliente
from alquiler.ai.demanda import predecir_demanda
from alquiler.ai.mantenimiento import recomendar_mantenimiento
from alquiler.ai.resultado import Resultado
from alquiler.ai.retrasos import analizar_retrasos
from alquiler.errors import PermisoDenegado, ReglaNegocioError
from alquiler.probar_ia import probar_ia
from alquiler.ui.logica.contexto import Contexto

CARPETA_CLAVE = configuracion.CARPETA_USUARIO

PREDEFINIDAS: list[tuple[str, str]] = [(c.id, c.titulo) for c in consultas.CONSULTAS_PREDEFINIDAS]
TITULO_ESTADO = {
    "ok": "Respuesta",
    "sin_datos": "Sin resultados",
    "aclaracion": "Se necesita una aclaración",
    "no_resoluble": "No se puede responder con estos datos",
    "sin_api": "IA no configurada",
    "error": "No se pudo completar la consulta",
}


def _texto(valor) -> str:
    if isinstance(valor, dict):
        return ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in valor.items())
    if isinstance(valor, list | tuple):
        return ", ".join(map(str, valor))
    return str(valor)


def tarjeta(resultado: Resultado, **extra) -> dict:
    indicadores = [(clave.replace("_", " ").capitalize(), _texto(valor))
                   for clave, valor in resultado.indicadores.items() if not clave.endswith("_id")]
    return {
        "resumen": resultado.resumen, "valor": resultado.valor,
        "confianza": resultado.confianza.value, "justificacion": list(resultado.justificacion),
        "advertencia": resultado.advertencia, "indicadores": indicadores,
        "prioridad": resultado.indicadores.get("prioridad"), **extra,
    }


# ---------------------------------------------------------------- analizadores
def demanda(ctx: Contexto) -> dict:
    tarjetas = ctx.ejecutar(lambda s, a: [tarjeta(r) for r in predecir_demanda(s, a, hoy=ctx.hoy())])
    resumen = (f"Pronóstico de alquileres para el próximo mes en {len(tarjetas)} categorías."
               if tarjetas else "No hay categorías registradas.")
    return {"resumen": resumen, "tarjetas": tarjetas}


def mantenimiento(ctx: Contexto) -> dict:
    tarjetas = ctx.ejecutar(lambda s, a: [tarjeta(r) for r in recomendar_mantenimiento(s, a, hoy=ctx.hoy())])
    resumen = (f"{len(tarjetas)} equipos superan el umbral de revisión (50 puntos)."
               if tarjetas else "Ningún equipo supera el umbral de revisión (50 puntos).")
    return {"resumen": resumen, "tarjetas": tarjetas}


def retrasos(ctx: Contexto) -> dict:
    analisis = ctx.ejecutar(lambda s, a: analizar_retrasos(s, a))
    if analisis.n_devoluciones == 0:
        return {"resumen": "Sin devoluciones registradas: no hay patrones que analizar.",
                "tarjetas": []}
    tasa = f"{100 * analisis.tasa_global:.1f} %".replace(".", ",")
    resumen = (f"Tasa global de devoluciones tardías: {tasa} sobre {analisis.n_devoluciones} "
               f"devoluciones. {len(analisis.clientes_marcados)} clientes con patrón de retraso.")
    tarjetas = ([tarjeta(r, grupo="Cliente") for r in analisis.clientes_marcados]
                + [tarjeta(r, grupo="Categoría") for r in analisis.por_categoria])
    return {"resumen": resumen, "tarjetas": tarjetas}


# ---------------------------------------------------------------- consola
def ia_disponible(ctx: Contexto) -> bool:
    return ctx.cliente_llm is not None


def puede_conectar_ia(ctx: Contexto) -> bool:
    return ctx.puede("usuarios.gestionar")  # la clave es del sistema: solo el administrador


def conectar_ia(ctx: Contexto, clave: str) -> str:
    """Prueba la clave con una llamada real; si responde, la guarda y activa la IA ya mismo.

    La clave queda en la carpeta del usuario (``~/.alquiler_equipos/alquiler.env``), así que la
    app descargada (un solo .exe o la app de macOS) la encuentra en cada arranque.
    """
    if not puede_conectar_ia(ctx):
        raise PermisoDenegado("Solo un administrador puede conectar la IA.")
    clave = (clave or "").strip()
    if not clave:
        raise ReglaNegocioError("Pegue la clave de Groq (empieza por gsk_).")
    nueva = dataclasses.replace(ctx.config, groq_api_key=clave, origen_clave="la aplicación")
    mensajes: list[str] = []
    if probar_ia(nueva, imprimir=mensajes.append) != 0:
        detalle = mensajes[-1] if mensajes else "La IA no respondió."
        raise ReglaNegocioError(detalle.replace("IA NO DISPONIBLE: ", ""))
    try:
        configuracion.guardar_clave(clave, CARPETA_CLAVE)
    except (ValueError, OSError) as e:
        raise ReglaNegocioError(f"La clave funciona, pero no se pudo guardar: {e}") from None
    ctx.config = nueva
    ctx.cliente_llm = crear_cliente(nueva)
    return mensajes[-1] if mensajes else "IA conectada."


def _respuesta(r: consultas.RespuestaConsulta) -> dict:
    columnas = [(f"c{i}", nombre) for i, nombre in enumerate(r.columnas)]
    filas = []
    for fila in r.filas:
        datos = {}
        for i, valor in enumerate(fila):
            datos[f"c{i}"] = "" if valor is None else str(valor)
            datos[f"c{i}__orden"] = valor if isinstance(valor, int | float) else datos[f"c{i}"]
        filas.append(datos)
    return {
        "estado": r.estado, "titulo_estado": TITULO_ESTADO[r.estado], "pregunta": r.pregunta,
        "respuesta": r.respuesta, "pasos": list(r.pasos), "sql": r.sql or "",
        "columnas": columnas, "filas": filas, "truncado": r.truncado,
        "advertencia": r.advertencia, "sugerencias": list(r.sugerencias),
    }


def preguntar(ctx: Contexto, texto: str) -> dict:
    return _respuesta(ctx.ejecutar(lambda s, a: consultas.consultar(
        s, a, texto, ctx.cliente_llm, ctx.config.db_path, hoy=ctx.hoy())))


def predefinida(ctx: Contexto, id_: str) -> dict:
    return _respuesta(ctx.ejecutar(lambda s, a: consultas.ejecutar_predefinida(
        s, a, id_, ctx.config.db_path, hoy=ctx.hoy())))
