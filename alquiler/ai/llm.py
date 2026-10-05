"""Cliente del modelo de lenguaje (Groq) con salida JSON estricta (spec §6.4 y Fase 6 §4.1).

``ClienteLLM`` es la interfaz mínima que usa el orquestador; las pruebas la
sustituyen por un cliente falso para no llamar a la red.
"""

import json
from typing import Protocol

import groq

from alquiler.config import Config
from alquiler.errors import ReglaNegocioError


class ErrorIA(ReglaNegocioError):
    """El servicio de IA no está disponible o respondió algo inutilizable."""


class ClienteLLM(Protocol):
    def generar_json(self, sistema: str, mensajes: list[dict], esquema: dict) -> dict: ...


_FORMATO_INESPERADO = "La IA devolvió una respuesta con formato inesperado."


def _codigo_error(error: Exception) -> str | None:
    cuerpo = getattr(error, "body", None)
    if isinstance(cuerpo, dict):
        detalle = cuerpo.get("error", cuerpo)
        if isinstance(detalle, dict):
            return detalle.get("code")
    return None


class ClienteGroq:
    def __init__(self, api_key: str, modelo: str, timeout: float, max_retries: int,
                 http_client=None):
        self.modelo, self.timeout, self.max_retries = modelo, timeout, max_retries
        opciones = {"http_client": http_client} if http_client is not None else {}
        # El SDK reintenta 429/5xx/errores de red con backoff exponencial.
        self._api = groq.Groq(api_key=api_key, timeout=timeout, max_retries=max_retries,
                              **opciones)

    def generar_json(self, sistema: str, mensajes: list[dict], esquema: dict) -> dict:
        try:
            respuesta = self._api.chat.completions.create(
                model=self.modelo,
                messages=[{"role": "system", "content": sistema}, *mensajes],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": "respuesta", "strict": True,
                                                 "schema": esquema}},
                temperature=0,
                max_completion_tokens=4096,
            )
        # Orden importante: las subclases antes que APIStatusError.
        except (groq.AuthenticationError, groq.PermissionDeniedError):
            raise ErrorIA("La clave de Groq no es válida o no tiene permisos; "
                          "revise GROQ_API_KEY.") from None
        except groq.RateLimitError:
            raise ErrorIA("Se alcanzó el límite de uso de Groq; espere un momento "
                          "o use las consultas predefinidas.") from None
        except groq.NotFoundError:
            raise ErrorIA("El modelo configurado en GROQ_MODEL no existe "
                          "o no está disponible.") from None
        except groq.BadRequestError as e:
            if _codigo_error(e) == "json_validate_failed":  # fallo puntual del modelo
                raise ErrorIA("La IA no produjo una respuesta válida; intente de nuevo.") from None
            raise ErrorIA("Groq rechazó la solicitud (formato o modelo no compatible).") from None
        except groq.APIConnectionError:  # incluye APITimeoutError
            raise ErrorIA("Sin conexión con Groq o tiempo agotado; "
                          "puede usar las consultas predefinidas.") from None
        except groq.APIStatusError as e:
            raise ErrorIA(f"El servicio de IA respondió con un error (código {e.status_code}).") from None
        except groq.APIError:  # p. ej. APIResponseValidationError
            raise ErrorIA(_FORMATO_INESPERADO) from None

        # Un portal cautivo o un proxy pueden responder 200 con HTML: el SDK entrega el texto.
        if not getattr(respuesta, "choices", None):
            raise ErrorIA(_FORMATO_INESPERADO)
        eleccion = respuesta.choices[0]
        if eleccion.finish_reason == "length":
            raise ErrorIA("La respuesta de la IA quedó incompleta; "
                          "intente con una pregunta más concreta.")
        try:
            datos = json.loads(eleccion.message.content or "")
        except json.JSONDecodeError:
            datos = None
        if not isinstance(datos, dict):
            raise ErrorIA(_FORMATO_INESPERADO)
        return datos


def crear_cliente(config: Config) -> ClienteLLM | None:
    """Devuelve el cliente configurado, o ``None`` si no hay clave (modo predefinidas)."""
    if not config.groq_api_key:
        return None
    return ClienteGroq(config.groq_api_key, config.groq_model,
                       config.groq_timeout, config.groq_max_retries)
