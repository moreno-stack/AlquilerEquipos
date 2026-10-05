"""``--probar-ia``: comprueba con una llamada real que la clave de Groq funciona.

Es el único camino del programa que usa la red a propósito sin que el usuario
haga una pregunta. No importa Qt, para que funcione también sin pantalla.
"""

from collections.abc import Callable

from alquiler.ai.llm import ClienteLLM, ErrorIA, crear_cliente
from alquiler.config import NOMBRE_ARCHIVO_ENV, Config

_ESQUEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"], "additionalProperties": False}

_COMO_CONFIGURAR = f"""La IA no está configurada: falta GROQ_API_KEY.

Para activarla:
  1. Cree una clave en https://console.groq.com/keys
  2. Copie {NOMBRE_ARCHIVO_ENV}.ejemplo como {NOMBRE_ARCHIVO_ENV} (junto al programa)
     y pegue la clave en la línea GROQ_API_KEY=
  3. Vuelva a ejecutar este comando con --probar-ia
(También puede definir la variable de entorno GROQ_API_KEY.)"""


def probar_ia(config: Config, crear: Callable[[Config], ClienteLLM | None] = crear_cliente,
              imprimir: Callable[[str], object] = print) -> int:
    """0: la IA responde; 1: error del servicio o respuesta inválida; 2: no hay clave."""
    if not config.groq_api_key:
        imprimir(_COMO_CONFIGURAR)
        return 2
    cliente = crear(config)
    clave = "…" + config.groq_api_key[-4:]
    imprimir(f"Probando Groq con el modelo {config.groq_model} (clave {clave}, "
             f"origen: {config.origen_clave})…")
    try:
        datos = cliente.generar_json(
            'Responde exactamente {"ok": true}.',
            [{"role": "user", "content": "Prueba de conexión."}], _ESQUEMA)
    except ErrorIA as e:
        imprimir(f"IA NO DISPONIBLE: {e}")
        return 1
    if datos.get("ok") is not True:
        imprimir("IA NO DISPONIBLE: la respuesta de prueba no fue la esperada.")
        return 1
    imprimir(f"IA OK: Groq responde con el modelo {config.groq_model} "
             f"(clave {clave}, origen: {config.origen_clave}).")
    return 0
