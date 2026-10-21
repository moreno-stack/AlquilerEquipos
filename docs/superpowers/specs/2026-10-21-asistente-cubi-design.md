# Asistente "Cubi" — diseño

Aprobado por Samuel el 2026-10-21. Se construye por fases y él confirma cada una antes de seguir.

## Objetivo

Un chatbot para **todos los roles** que contesta preguntas sobre el negocio y sobre cómo usar el sistema. Usa la IA de Groq. Vive en una burbuja flotante y su avatar animado tiene voz.

## Fases

| Fase | Contenido |
|---|---|
| A | Archivo `alquiler.env` con la clave de Groq (la pega el usuario). |
| B | Cerebro: `alquiler/ai/asistente.py` con herramientas por rol, protocolo JSON y preguntas rápidas sin IA, más `alquiler/ui/logica/asistente.py`. |
| C | Avatar animado y panel flotante con animaciones. |
| D | Voz con QtTextToSpeech de Windows, sin conexión: boca sincronizada, botón para silenciar y ajuste del `.exe`. |

## Seguridad (fase B)

- **El modelo nunca escribe SQL ni toca la base**, salvo con la herramienta `consulta_libre`, que es solo para el administrador y reutiliza el Text-to-SQL validado de la Consola IA.
- **Las herramientas son de solo lectura** y llaman a los servicios, que vuelven a comprobar el permiso. El prompt solo ofrece las herramientas del rol. Si el modelo pide otra, recibe el mensaje "no está disponible".
- **El cliente solo ve** `equipos_disponibles` y `mis_alquileres`, que se filtran por su `cliente_id`.
- **Límites:**
  - como máximo `MAX_PASOS` = 3 herramientas por pregunta;
  - `MAX_HISTORIAL` = 10 mensajes de historial;
  - 500 caracteres por mensaje;
  - 12 filas por herramienta.
- **Los analizadores** se ejecutan con `persistir=False`: preguntar no escribe nada en la base.
- **Sin clave de IA:** el estado es `sin_api` y se ofrecen las preguntas rápidas por rol, que se responden con textos fijos.

## Protocolo con el modelo

El modelo responde con este esquema estricto:

```json
{"tipo": "herramienta" | "respuesta",
 "herramienta": <enum del rol> | "ninguna",
 "argumento": str,
 "respuesta": str,
 "emocion": "feliz" | "neutral" | "pensativo" | "preocupado" | "confundido"}
```

La `emocion` decide la cara que pone el avatar en la fase C.
