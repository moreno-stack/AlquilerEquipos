# Sistema de diseño "Centro de control"

Sistema Inteligente de Alquiler de Equipos · v1 (2026-10-05)

Los valores viven en **`diseno/tokens.css`**, la única fuente de verdad. La aplicación de escritorio (`alquiler/ui/tema.py`) y la página de componentes (`diseno/styleguide.html`) leen ese archivo.

> **Regla de oro:** ninguna pantalla define un color, una medida ni un tiempo a mano; todas usan las variables. Una prueba automática lo vigila: `tests/ui/test_tema.py` falla si aparece un color hexadecimal fuera de `tokens.css`.

## 1. Principios

1. **Herramienta de trabajo, no vitrina.** Los datos mandan y la decoración no compite con ellos.
2. **Un solo color vivo.** El cian marca lo que se puede tocar o lo que está activo. Si todo resalta, nada resalta.
3. **Profundidad por tono.** Las capas se distinguen subiendo un escalón de azul pizarra, no con sombras pesadas.
4. **El color nunca va solo.** Todo estado comunicado con color lleva también un ícono, un signo o un texto (ver §8).
5. **Movimiento con propósito.** Solo confirma una acción u orienta la vista. Siempre es breve y se puede desactivar.

## 2. Color

### 2.1 Superficies

Van de más oscura a más clara; cada capa se apoya sobre la anterior.

| Variable | Valor | Uso |
|---|---|---|
| `--color-fondo-hundido` | `#040814` | Menú lateral, barra de estado |
| `--color-fondo` | `#060B1A` | Fondo de la ventana |
| `--color-superficie` | `#0D1630` | Tarjetas, tablas, campos |
| `--color-superficie-alta` | `#15213F` | Filas alternas, botón secundario, hover |
| `--color-borde` | `#1E2B4D` | Bordes de 1 px |
| `--color-borde-fuerte` | `#2E3D63` | Bordes de campos y botones |
| `--color-rejilla` | `#1A2647` | Líneas de tablas y gráficos |

### 2.2 Texto

| Variable | Valor | Uso |
|---|---|---|
| `--color-texto` | `#E2E8F0` | Texto principal |
| `--color-texto-secundario` | `#94A3B8` | Etiquetas, ayudas, subtítulos |
| `--color-texto-deshabilitado` | `#64748B` | Solo controles deshabilitados (exentos del 4.5:1 según WCAG) |

### 2.3 Acento y peligro

| Variable | Valor | Uso |
|---|---|---|
| `--color-acento` | `#22D3EE` | Botón primario, sección activa, foco, gráficos |
| `--color-acento-hover` | `#67E8F9` | Hover del botón primario |
| `--color-sobre-acento` | `#020617` | Texto e íconos sobre el acento |
| `--color-acento-suave` / `--color-acento-texto` | `#083344` / `#67E8F9` | Avisos de marca ("IA: Groq conectada") |
| `--color-secundario` | `#A78BFA` | Violeta para detalles puntuales (pestañas al pasar el cursor) |
| `--color-seleccion` | `#0E7490` | Fila seleccionada, con texto blanco |
| `--color-peligro` | `#FB7185` | Texto y borde de acciones destructivas |
| `--color-peligro-fuerte` | `#BE123C` | Relleno del botón de peligro al pasar el cursor, con texto blanco |

**Uso:** como máximo **un** botón primario por barra de acciones. Las acciones destructivas nunca usan el acento.

### 2.4 Transparencias

| Variable | Uso |
|---|---|
| `--color-brillo` | Barrido del esqueleto de carga, reflejo superior de las tarjetas |
| `--color-acento-halo` | Resplandor suave detrás del elemento activo |
| `--color-velo` | Fondo oscurecido detrás de los diálogos |

### 2.5 Estados del equipo

Cada estado tiene tres valores:
- **fuerte:** barras, franjas y puntos;
- **fondo:** fondo de la etiqueta;
- **texto:** texto de la etiqueta.

| Estado | Prefijo | Fuerte | Fondo | Texto | Segunda señal (§8) |
|---|---|---|---|---|---|
| Disponible | `--estado-disponible-*` | `#34D399` | `#064E3B` | `#A7F3D0` | ícono ✓ |
| Alquilado | `--estado-alquilado-*` | `#60A5FA` | `#1E3A8A` | `#BFDBFE` | ícono ↗ |
| Reservado | `--estado-reservado-*` | `#A78BFA` | `#4C1D95` | `#DDD6FE` | ícono ◷ |
| En mantenimiento | `--estado-mantenimiento-*` | `#FBBF24` | `#78350F` | `#FDE68A` | ícono 🔧 (llave) |
| Fuera de servicio | `--estado-fuera-*` | `#FB7185` | `#881337` | `#FECDD3` | ícono ✕ |

### 2.6 Degradado de marca

El toque llamativo de la interfaz: el cian se funde en violeta a 135°.

| Variable | Valor | Uso |
|---|---|---|
| `--degradado-marca` | cian `#22D3EE` → violeta `#A78BFA` | Botón primario, sección activa del menú, logo, números de sección, título principal, medidor de confianza |
| `--degradado-marca-hover` | `#67E8F9` → `#C4B5FD` | Botón primario al pasar el cursor |
| `--color-aurora-cian` / `--color-aurora-violeta` | cian 16 % / violeta 14 % | Resplandor difuso del fondo y halo de las tarjetas activas |

**Reglas:**

- **Dónde va:** solo en lo que guía la vista. Nunca en párrafos ni en datos de tablas.
- **Texto encima:** siempre en `--color-sobre-acento`. Cumple 4.5:1 en los **dos extremos** del degradado, y lo verifica una prueba.
- **Cuántos por pantalla:** como máximo un botón con degradado; los demás botones son secundarios.

### 2.7 Vidrio esmerilado y neón (estilo centro de control)

Los paneles del tablero son **translúcidos** sobre un **fondo de red de datos**: un degradado de azul medianoche con auroras cian, azul eléctrico y púrpura, y nodos unidos por líneas tenues. El fondo se pinta en `alquiler/ui/centro.py` (`FondoCosmico`) y siempre es el mismo dibujo, porque usa una semilla fija.

| Variable | Valor | Uso |
|---|---|---|
| `--color-vidrio` | azul medianoche al 62 % | Fondo de paneles y tarjetas |
| `--color-vidrio-alto` | al 78 % | Panel al pasar el cursor, filas alternas del monitor |
| `--color-vidrio-borde` | cian al 22 % | Borde neón de 1 px de los paneles |
| `--color-neon-halo` / `--color-purpura-halo` | cian 35 % / púrpura 30 % | Resplandor alrededor de paneles y del botón de diagnóstico |
| `--color-azul-electrico` | `#3B82F6` | Auroras del fondo, detalles |
| `--color-purpura-neon` | `#A855F7` | Segunda serie de gráficos, brillos |

**Reglas:**

- **Púrpura neón:** solo en líneas, brillos y auroras. Nunca va detrás de texto, porque con texto oscuro no llega a 4.5:1.
- **Texto sobre vidrio:** el fondo efectivo es aún más oscuro que `--color-superficie`, así que sus contrastes se cumplen con margen.
- **Tablas largas y diálogos:** usan superficie opaca, no vidrio, para que se lean bien.

## 3. Tipografía

Las fuentes se definen en el paso 6 y van guardadas dentro del proyecto, no se cargan de internet.

| Variable | Fuente | Uso |
|---|---|---|
| `--fuente-titulos` | Manrope (SIL OFL) | Títulos de pantalla, saludos, cifras grandes |
| `--fuente-texto` | Inter (SIL OFL) | Todo lo demás |
| `--fuente-numeros` | Inter con cifras tabulares | Montos y conteos en tablas (alineados) |

| Variable | Tamaño | Uso típico |
|---|---|---|
| `--texto-xs` | 12 px | Leyendas, avisos de IA |
| `--texto-sm` | 13 px | Etiquetas, encabezados de tabla |
| `--texto-base` | 14 px | Cuerpo, celdas |
| `--texto-md` | 16 px | Subtítulos de tarjeta |
| `--texto-lg` | 20 px | Títulos internos |
| `--texto-xl` | 24 px | Título de pantalla |
| `--texto-2xl` | 32 px | Cifras de indicadores |

- **Pesos:** `--peso-normal` (400), `--peso-medio` (600) y `--peso-fuerte` (700).
- **Interlineado:** 1.2 en títulos y 1.5 en texto.

## 4. Espaciado

Base de 4 px: `--espacio-1` (4), `-2` (8), `-3` (12), `-4` (16), `-5` (20), `-6` (24), `-8` (32), `-10` (40) y `-12` (48).

| Situación | Token |
|---|---|
| Relleno interno de tarjeta | `--espacio-4` a `--espacio-6` |
| Separación entre tarjetas de una rejilla | `--espacio-3` |
| Separación entre secciones de una pantalla | `--espacio-6` |
| Margen de la ventana | `--espacio-6` |
| Separación entre ícono y texto | `--espacio-2` |

## 5. Radios de borde

| Variable | Valor | Uso |
|---|---|---|
| `--radio-sm` | 6 px | Casillas, etiquetas cuadradas |
| `--radio-md` | 8 px | Botones, campos, ítems del menú |
| `--radio-lg` | 12 px | Tarjetas, paneles, diálogos |
| `--radio-pildora` | 999 px | Etiquetas de estado |

## 6. Sombras

En un tema oscuro, la sombra apenas se ve: la profundidad la da el tono (§1.3).

| Variable | Uso |
|---|---|
| `--sombra-1` | Tarjeta al pasar el cursor |
| `--sombra-2` | Menús desplegables, diálogos |
| `--sombra-foco` | Anillo de foco del teclado (cian al 40 %); **siempre visible** al navegar con Tab |

## 7. Movimiento

| Variable | Valor | Uso |
|---|---|---|
| `--duracion-rapida` | 120 ms | Hover y presionar |
| `--duracion-base` | 200 ms | Mostrar u ocultar elementos pequeños |
| `--duracion-lenta` | 320 ms | Entrada de tarjetas y paneles |
| `--curva-salida` | `cubic-bezier(.2,.8,.2,1)` | Entradas |
| `--curva-entrada-salida` | `cubic-bezier(.4,0,.2,1)` | Cambios de estado |
| `--desplazamiento-entrada` | 12 px | Recorrido máximo de una entrada |

**Reglas:**
1. Solo se animan `transform` y `opacity`, nunca tamaño, márgenes ni colores de fondo. Así la animación es fluida en equipos de gama media.
2. Una entrada no dura más de `--duracion-lenta`. Los elementos de una lista entran escalonados con, como máximo, 40 ms entre uno y otro.
3. Con `prefers-reduced-motion: reduce`, todas las duraciones pasan a 0 y la interfaz se muestra estática; `tokens.css` ya lo hace.
4. Cada animación ligada al desplazamiento se destruye al salir de su pantalla (paso 5).
5. Nunca se anima algo que el usuario está leyendo o editando.

**En la aplicación de escritorio** (`alquiler/ui/animacion.py`, que lee estas mismas duraciones):

| Animación | Dónde | Duración |
|---|---|---|
| Fundido de entrada | Cada sección al abrirla | `--duracion-base` |
| Cascada (fundido escalonado, 40 ms entre bloques) | Tarjetas y paneles de Inicio | `--duracion-lenta` cada uno |
| Cifras que cuentan desde 0 y barras que se llenan | Indicadores y ocupación por categoría | 3 × `--duracion-lenta` (excepción: es un dato que se lee al final, no una entrada) |
| Dona que gira y líneas que crecen | Utilización y tendencia | 3 × `--duracion-lenta` |
| Brillo neón que se intensifica | Tarjetas, botón de diagnóstico y botón INGRESAR al pasar el cursor | `--duracion-base` |
| Temblor | Panel de ingreso con usuario o contraseña incorrectos | `--duracion-lenta` + `--duracion-rapida` |
| Red de datos que flota y nodos que laten | Fondo cósmico (portada y sistema) | Continua, solo mientras se ve |
| Presentación y panel en cascada (160 ms) | Portada de ingreso | `--duracion-lenta` |

Equivalente de `prefers-reduced-motion`: la variable de entorno `ALQUILER_ANIMACIONES=0` apaga todo el movimiento (también se apaga sin pantalla, como en las pruebas). Cada animación termina siempre en el valor exacto, así que apagarla no cambia lo que se ve al final.

## 8. Accesibilidad (resumen; detalle en el paso 4)

- Todo texto cumple al menos **4.5:1** sobre su fondo, y las barras y bordes de componentes al menos **3:1**. Lo verifica `tests/ui/test_tema.py`.
- **El color nunca es la única pista:**
  - las etiquetas de estado llevan ícono y texto;
  - las barras de gráficos llevan una trama distinta por serie, además del color;
  - los errores llevan un ícono ⚠ y un mensaje.
- El foco del teclado siempre es visible (`--sombra-foco`).

## 9. Cómo lo usa cada parte del proyecto

| Parte | Cómo consume los tokens |
|---|---|
| `alquiler/ui/tema.py` | Lee `tokens.css` al arrancar y construye con él la hoja de estilo de Qt |
| `diseno/styleguide.html` | `<link rel="stylesheet" href="tokens.css">` |
| Ejecutable (PyInstaller) | `AlquilerEquipos.spec` empaqueta `diseno/tokens.css` |
