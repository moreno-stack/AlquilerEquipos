"""Cliente de Groq con salida JSON estricta. Sin red: httpx.MockTransport."""

import json

import httpx
import pytest

from alquiler.ai import llm, prompts
from alquiler.config import cargar_config

ESQUEMA = {"type": "object", "properties": {"respuesta": {"type": "string"}},
           "required": ["respuesta"], "additionalProperties": False}
MENSAJES = [{"role": "user", "content": "hola"}]


def _completado(contenido, fin: str = "stop") -> dict:
    return {"id": "chatcmpl-1", "object": "chat.completion", "created": 0,
            "model": "openai/gpt-oss-20b",
            "choices": [{"index": 0, "finish_reason": fin,
                         "message": {"role": "assistant", "content": contenido}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


def _error(mensaje: str = "x") -> dict:
    return {"error": {"message": mensaje, "type": "invalid_request_error"}}


def _cliente(respuestas, peticiones=None, max_retries=0):
    respuestas = list(respuestas)

    def manejar(request: httpx.Request) -> httpx.Response:
        if peticiones is not None:
            peticiones.append(request)
        estado, cuerpo = respuestas.pop(0)
        return httpx.Response(estado, json=cuerpo)

    return llm.ClienteGroq(api_key="gsk_test", modelo="openai/gpt-oss-20b", timeout=5,
                           max_retries=max_retries,
                           http_client=httpx.Client(transport=httpx.MockTransport(manejar)))


def test_peticion_estructurada():
    peticiones = []
    c = _cliente([(200, _completado('{"respuesta": "ok"}'))], peticiones)
    assert c.generar_json("SYS", MENSAJES, ESQUEMA) == {"respuesta": "ok"}
    [peticion] = peticiones
    assert str(peticion.url).endswith("/openai/v1/chat/completions")
    assert peticion.headers["authorization"] == "Bearer gsk_test"
    cuerpo = json.loads(peticion.content)
    assert cuerpo["model"] == "openai/gpt-oss-20b"
    assert cuerpo["messages"][0] == {"role": "system", "content": "SYS"}
    assert cuerpo["messages"][1:] == MENSAJES
    formato = cuerpo["response_format"]
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["strict"] is True
    assert formato["json_schema"]["schema"] == ESQUEMA
    assert cuerpo["temperature"] == 0
    assert cuerpo["max_completion_tokens"] == 4096


def test_respuesta_truncada():
    c = _cliente([(200, _completado('{"respuesta": "a', fin="length"))])
    with pytest.raises(llm.ErrorIA, match="incompleta"):
        c.generar_json("s", MENSAJES, ESQUEMA)


@pytest.mark.parametrize("contenido", [None, "", "no json", "[1, 2]", '"texto"'])
def test_contenido_invalido(contenido):
    c = _cliente([(200, _completado(contenido))])
    with pytest.raises(llm.ErrorIA, match="formato inesperado"):
        c.generar_json("s", MENSAJES, ESQUEMA)


@pytest.mark.parametrize("estado, fragmento", [
    (401, "clave de Groq no es válida"),
    (403, "clave de Groq no es válida"),
    (429, "límite de uso de Groq"),
    (404, "GROQ_MODEL"),
    (400, "Groq rechazó la solicitud"),
    (503, r"código 503"),
])
def test_traduccion_de_errores(estado, fragmento):
    c = _cliente([(estado, _error())])
    with pytest.raises(llm.ErrorIA, match=fragmento) as error:
        c.generar_json("s", MENSAJES, ESQUEMA)
    assert "gsk_test" not in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__


def test_sin_conexion():
    def caido(request):
        raise httpx.ConnectError("sin red", request=request)

    c = llm.ClienteGroq("gsk_test", "m", 5, 0,
                        http_client=httpx.Client(transport=httpx.MockTransport(caido)))
    with pytest.raises(llm.ErrorIA, match="Sin conexión con Groq"):
        c.generar_json("s", MENSAJES, ESQUEMA)


def test_reintenta_ante_500():
    peticiones = []
    c = _cliente([(500, _error("boom")), (200, _completado('{"respuesta": "ok"}'))],
                 peticiones, max_retries=1)
    assert c.generar_json("s", MENSAJES, ESQUEMA) == {"respuesta": "ok"}
    assert len(peticiones) == 2


@pytest.mark.parametrize("esquema", [prompts.ESQUEMA_GENERACION, prompts.ESQUEMA_RESPUESTA])
def test_esquemas_compatibles_con_modo_estricto(esquema):
    """El modo estricto de Groq exige todos los campos en required y sin propiedades extra."""
    assert set(esquema["required"]) == set(esquema["properties"])
    assert esquema["additionalProperties"] is False


def test_crear_cliente_sin_clave_devuelve_none():
    assert llm.crear_cliente(cargar_config({}, archivo=False)) is None


def test_crear_cliente_con_clave_usa_la_config():
    cfg = cargar_config({"GROQ_API_KEY": "gsk_x", "GROQ_TIMEOUT": "9",
                         "GROQ_MAX_RETRIES": "4"}, archivo=False)
    c = llm.crear_cliente(cfg)
    assert isinstance(c, llm.ClienteGroq)
    assert (c.modelo, c.timeout, c.max_retries) == ("openai/gpt-oss-20b", 9.0, 4)


# ---------------------------------------------------------------- hallazgos de la revisión
@pytest.mark.parametrize("cuerpo", ["<html>Portal de acceso de la universidad</html>", "[1, 2]"])
def test_respuesta_200_que_no_es_un_completado(cuerpo):
    """Un portal cautivo o un proxy pueden responder 200 con HTML: nunca una excepción cruda."""
    def manejar(request):
        return httpx.Response(200, text=cuerpo, headers={"content-type": "text/html"})

    c = llm.ClienteGroq("gsk_test", "m", 5, 0,
                        http_client=httpx.Client(transport=httpx.MockTransport(manejar)))
    with pytest.raises(llm.ErrorIA, match="formato inesperado"):
        c.generar_json("s", MENSAJES, ESQUEMA)


def test_json_invalido_segun_el_esquema_sugiere_reintentar():
    cuerpo = {"error": {"message": "Failed to validate JSON", "type": "invalid_request_error",
                        "code": "json_validate_failed"}}
    c = _cliente([(400, cuerpo)])
    with pytest.raises(llm.ErrorIA, match="intente de nuevo"):
        c.generar_json("s", MENSAJES, ESQUEMA)
