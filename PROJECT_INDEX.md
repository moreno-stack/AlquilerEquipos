# Índice del proyecto — Sistema Inteligente de Alquiler de Equipos

Mapa del repositorio por capas: qué hace cada archivo, cómo fluye una operación y cómo probar
cada parte.

`tests/test_documentacion.py` mantiene este índice sincronizado con el código. Falla si una ruta
citada no existe o si un módulo o archivo de pruebas nuevo no aparece aquí.

- Estado: Fases 1–5 completas.
- Versión: 0.1.0.
- Diseño: `docs/superpowers/specs/2026-10-04-alquiler-equipos-design.md`.
- Plan y decisiones por tarea: `docs/superpowers/plans/2026-10-04-alquiler-equipos.md`.

## Arquitectura en una imagen

```
            ┌───────────────────────────── alquiler/ui ─────────────────────────────┐
 usuario →  │  vistas/ (Qt)  ──►  logica/ (sin Qt)  ──►  Contexto.ejecutar(fn)       │
            │  trabajador.py: QThreadPool → resultado al hilo GUI por señales        │
            └──────────────────────────────────┬─────────────────────────────────────┘
                                               │ sesión SQLAlchemy por operación
                     ┌─────────────────────────┴───────────────────────┐            (rollback ante error)
                     ▼                                                 ▼
          alquiler/services (reglas, RBAC)              alquiler/ai (estimaciones, Text-to-SQL)
                     │                                                 │      └─► API de Groq (opcional)
                     └──────────────► models / db / auth ◄─────────────┘
                                              │
                                     SQLite + Alembic (migrations/)
```

**Reglas de dependencia:**
- Las vistas Qt **solo** importan `alquiler.ui.*` y `alquiler.errors`; `tests/ui/test_arquitectura.py`
  lo verifica.
- Los servicios verifican el permiso, validan todas las reglas y recién entonces escriben. Cualquier
  violación lanza `ReglaNegocioError`.
- La IA nunca escribe en tablas de negocio; solo persiste `RecomendacionIA`.

---

## Fase 1 — Base: configuración, datos y autenticación

| Archivo | Responsabilidad |
|---|---|
| `alquiler/__init__.py` | Versión del paquete. |
| `alquiler/__main__.py` | `python -m alquiler` → `alquiler.ui.app.main()`. |
| `alquiler/config.py` | `Config` desde variables de entorno y el archivo `alquiler.env` (el entorno gana): BD, admin, mora y `GROQ_*`, con validación; `repr` enmascara la clave. |
| `alquiler/probar_ia.py` | `probar_ia`: comando `--probar-ia`; una llamada real a Groq para confirmar la clave (códigos 0/1/2). |
| `alquiler/db.py` | `Base` con convención de nombres, `crear_engine` (activa las FK de SQLite y crea la carpeta), `crear_sessionmaker` e `init_db` (Alembic `upgrade head`). |
| `alquiler/models.py` | Enums y las 9 entidades: Usuario, Cliente, Categoria, Equipo, Alquiler, Devolucion, Pago, Mantenimiento y RecomendacionIA, con sus restricciones CHECK, UNIQUE y FK. |
| `alquiler/errors.py` | `ReglaNegocioError`, `CredencialesInvalidas` y `PermisoDenegado`. Sus mensajes se muestran al usuario. |
| `alquiler/auth.py` | Contraseñas con bcrypt (8 caracteres a 72 bytes), `autenticar` (sin revelar si el usuario existe), la matriz `PERMISOS_POR_ROL` (15 permisos), `requerir_permiso` y el admin inicial. |
| `alquiler/migrations/env.py` | Entorno de Alembic: conexión inyectada por `init_db` o por `ALQUILER_DB_PATH` (CLI); modo batch para SQLite. |
| `alquiler/migrations/versions/0001_esquema_inicial.py` | Migración inicial: las 9 tablas. |

## Fase 2 — Servicios de negocio

| Archivo | Responsabilidad |
|---|---|
| `alquiler/services/__init__.py` | `obtener(session, Modelo, id)` y `pesos()` (formato COP). |
| `alquiler/services/equipos.py` | `TRANSICIONES` (máquina de estados, spec §4.3), `transicionar`, categorías y CRUD. El catálogo del cliente solo muestra equipos disponibles. |
| `alquiler/services/clientes.py` | Registro, autorregistro desde la portada (cliente + usuario en una sola transacción; no reclama documentos existentes), edición (el cliente solo su contacto), baja lógica (también bloquea su usuario) e historial. |
| `alquiler/services/alquileres.py` | Costos (`dias_contratados`, `calcular_costo`), crear (activo o reservado), entregar o cancelar una reserva, pagos limitados al saldo y vencidos. |
| `alquiler/services/devoluciones.py` | `liquidar` (retraso, mora con redondeo half-up, total) y `registrar_devolucion`: contadores de uso; con daños, abre un correctivo. |
| `alquiler/services/mantenimiento.py` | `abrir` (interno), abrir y cerrar preventivo o correctivo, historial. No se abre sobre un equipo alquilado. |
| `alquiler/services/reportes.py` | Ingresos por concepto y mes, uso de flota (intervalos `[inicio, fin)`) y morosidad. |
| `alquiler/services/usuarios.py` | Alta con RBAC, activar o desactivar (nunca a uno mismo), cambiar y restablecer contraseña. |

## Fase 3 — Motor de IA explicable

| Archivo | Responsabilidad |
|---|---|
| `alquiler/ai/__init__.py` | Paquete de IA. |
| `alquiler/ai/resultado.py` | `Resultado(resumen, valor, confianza, indicadores, justificacion, advertencia)`: el contrato de toda estimación. |
| `alquiler/ai/demanda.py` | Serie mensual por categoría, índice estacional × media desestacionalizada y rango del 80 % con piso de Poisson. |
| `alquiler/ai/mantenimiento.py` | Puntaje 0–100 (usos 35 %, días 25 %, uso reciente 15 %, fallas 25 %) con aporte por factor; persiste `RecomendacionIA` sin duplicar. |
| `alquiler/ai/retrasos.py` | Tasa suavizada `(r + k·p)/(n + k)` y clientes marcados si superan 2·p con n ≥ 3; análisis por categoría. |
| `alquiler/ai/sql_seguro.py` | Tres barreras: `validar_sql` (estático), conexión `mode=ro` y `set_authorizer`. Además: límite de 3 s, 200 filas y 100 KB por valor. |
| `alquiler/ai/prompts.py` | Esquema generado desde `Base.metadata` (sin `usuario`), reglas de negocio, protocolo de ambigüedad y esquemas JSON. |
| `alquiler/ai/llm.py` | `ClienteGroq`: SDK `groq` con `json_schema` estricto, timeout y reintentos; los errores se traducen a `ErrorIA`. |
| `alquiler/ai/consultas.py` | Orquestador Text-to-SQL: generar → validar y ejecutar (una corrección) → redactar. Devuelve `RespuestaConsulta` con estado y las 6 consultas predefinidas. |
| `alquiler/ai/asistente.py` | Asistente «Cubi»: herramientas de solo lectura por rol (catálogo, mis alquileres, resumen, vencidos, estimaciones, ingresos, consulta libre de admin), protocolo JSON con Groq (máx. 3 herramientas) y preguntas rápidas sin IA. |

## Fase 4 — Interfaz, concurrencia y datos demo

| Archivo | Responsabilidad |
|---|---|
| `alquiler/seed.py` | Simulación determinista de 18 meses **a través de los servicios reales**. CLI: `python -m alquiler.seed`. |
| `alquiler/ui/__init__.py` | Paquete de la interfaz. |
| `alquiler/ui/app.py` | Raíz de composición: `preparar_base`, `ofrecer_demo`, `fabricas_de_vistas`, `autoprueba` y `main` (con `--version` y `--autoprueba`). |
| `alquiler/ui/logica/__init__.py` | Capa de lógica de presentación (sin Qt). |
| `alquiler/ui/logica/contexto.py` | `Contexto.ejecutar(fn)`: una sesión por operación, rollback ante cualquier error y verificación de usuario activo. Incluye `iniciar_sesion`. |
| `alquiler/ui/logica/navegacion.py` | Las 11 secciones (Inicio primero) y su permiso; `secciones_para(ctx)`. |
| `alquiler/ui/logica/formato.py` | Pesos, fechas y niveles. |
| `alquiler/ui/logica/catalogo.py` | Equipos, estados posibles, categorías y mantenimiento. |
| `alquiler/ui/logica/personas.py` | Clientes (habilitados, historial con saldo), usuarios y perfil propio. |
| `alquiler/ui/logica/operaciones.py` | Cotización, alquileres con situación, vista previa de la devolución, pagos y reservas clasificadas. |
| `alquiler/ui/logica/reportes.py` | KPIs, ingresos por mes (mes parcial con `*`), uso de flota y vencidos. |
| `alquiler/ui/logica/ia.py` | Tarjetas de resultados de IA y adaptación de la consola. |
| `alquiler/ui/logica/asistente.py` | Adapta las respuestas de Cubi para la vista: texto, emoción, fuentes legibles y sugerencias. |
| `alquiler/ui/logica/inicio.py` | Pantalla de Inicio: `resumen(ctx)` por permisos (flota, operación, mantenimiento, ingresos del mes, alerta de IA sin persistir, "mis alquileres"), `tarjetas_kpi`, `fecha_larga` y `saludo_para`. |
| `alquiler/ui/trabajador.py` | `ejecutar_en_segundo_plano` con QThreadPool: el resultado vuelve al hilo GUI y se descarta si el widget ya se destruyó. |
| `alquiler/ui/tema.py` | Traduce a Qt los tokens de `diseno/tokens.css` (paleta, estados, QSS, `aplicar(app)` con Fusion oscuro); no escribe ningún color a mano. |
| `alquiler/ui/iconos.py` | Iconos vectoriales del menú (SVG en código, QtSvg) con color normal y de sección activa. |
| `alquiler/ui/centro.py` | Piezas del centro de control: `FondoCosmico` (red de datos), `Panel` de vidrio, `aplicar_brillo` (neón), `GraficoDona` y `GraficoTendencia`. |
| `alquiler/ui/widgets.py` | `ESTILO` (desde el tema), `marca`, `TarjetaKPI` y `BarraEstados` (Inicio), `configurar_locale` (es-CO), `Tabla`, `Insignia`, `TarjetaResultado`, `botones_dialogo` (protección contra doble clic) y `ejecutar_accion`. |
| `alquiler/ui/login.py` | Portada de ingreso: fondo cósmico animado, marca con degradado, beneficios y panel de vidrio con usuario y contraseña (tiembla ante un error) o formulario «Crear cuenta» de cliente. |
| `alquiler/ui/animacion.py` | Animaciones: fundido y entrada escalonada, cifras que cuentan, barras que se llenan, temblor y brillo al pasar el cursor; duraciones de `tokens.css`, apagadas sin pantalla o con `ALQUILER_ANIMACIONES=0`. |
| `alquiler/ui/logo.py` | Logo "cubo neural" dibujado en vector: cubo neón con nodos y núcleo de IA que late; `Logo` (widget), `pixmap_logo` e `icono_app` (ícono de las ventanas). |
| `alquiler/ui/ventana.py` | Ventana principal: barra lateral por rol, vistas perezosas, recarga al volver a una sección y espera de tareas al cerrar. |
| `alquiler/ui/vistas/__init__.py` | Paquete de vistas. |
| `alquiler/ui/vistas/equipos.py` | Catálogo, `PanelEstados` (máquina de estados visual) y diálogos de equipo, categoría y mantenimiento. |
| `alquiler/ui/vistas/mantenimiento.py` | Mantenimientos abiertos, cierre e historial por equipo. |
| `alquiler/ui/vistas/clientes.py` | Clientes e historial. |
| `alquiler/ui/vistas/alquileres.py` | Nuevo alquiler (cotización en vivo), devolución (mora en vivo) y pago. |
| `alquiler/ui/vistas/reservas.py` | Reservas pendientes, listas y vencidas; entregar y cancelar. |
| `alquiler/ui/vistas/reportes.py` | KPIs y gráficos QtCharts, generados en segundo plano. |
| `alquiler/ui/vistas/ia.py` | Análisis IA: pestañas con tarjetas explicables. |
| `alquiler/ui/vistas/inicio.py` | Tablero de control: KPI con ícono, tendencia de alquileres, utilización de la flota (dona), ocupación por categoría, alerta de IA y monitor de actividad; carga en segundo plano. |
| `alquiler/ui/vistas/consola_ia.py` | Consola IA: respuesta en dos partes, historial, consultas rápidas y sugerencias. |
| `alquiler/ui/vistas/usuarios.py` | Cuentas y roles. |
| `alquiler/ui/vistas/perfil.py` | Contraseña propia; contacto e historial del cliente. |

## Fase 5 — Documentación y empaquetado

| Archivo | Responsabilidad |
|---|---|
| `README.md` | Instalación, configuración, inicio rápido, privacidad, pruebas y empaquetado. |
| `PROJECT_INDEX.md` | Este mapa. |
| `diseno/DESIGN.md` | Sistema de diseño: principios, color, tipografía, espaciado, radios, sombras, movimiento y accesibilidad. |
| `diseno/tokens.css` | Variables CSS del sistema de diseño: única fuente de verdad visual (app de escritorio y styleguide). |
| `diseno/styleguide.html` | Página de componentes (botones, estados, tarjetas, formularios, listas, cargando/vacío/error, avisos) hecha solo con `tokens.css`. |
| `AlquilerEquipos.spec` | PyInstaller *onedir*: incluye las migraciones como datos, excluye los módulos de Qt no usados y copia `alquiler.env.ejemplo` junto al ejecutable. |
| `alquiler.env.ejemplo` | Plantilla de configuración: se copia como `alquiler.env` (ignorado por git) y se pega la clave de Groq. |
| `scripts/lanzador.py` | Punto de entrada del ejecutable. |
| `scripts/empaquetar.py` | Construye el ejecutable y lo verifica con `--autoprueba` en un entorno limpio. |
| `scripts/empaquetar_windows.bat` | Lo mismo en Windows. |

---

## Flujos principales

**Registrar una devolución:**

1. `vistas/alquileres.py` → `DialogoDevolucion`, con vista previa en vivo mediante
   `logica/operaciones.previsualizar_devolucion` → `devoluciones.liquidar`.
2. Guardar → `widgets.ejecutar_accion` → `logica/operaciones.registrar_devolucion` → `Contexto.ejecutar`.
3. Dentro de la sesión, `services/devoluciones.registrar_devolucion` hace lo siguiente:
   - verifica el permiso;
   - valida el estado, las fechas, las horas y los daños;
   - suma el uso del equipo;
   - con daños, `mantenimiento.abrir`; sin daños, `transicionar → Disponible`;
   - hace commit.
4. Si algo falla: rollback y mensaje en pantalla, sin traceback.

**Consulta en lenguaje natural:**

1. `vistas/consola_ia.py` → `trabajador` → `logica/ia.preguntar` → `ai/consultas.consultar`.
2. Generación: `llm.ClienteGroq` con `prompts.prompt_generacion` devuelve JSON con el SQL y los pasos.
3. Ejecución: `sql_seguro.validar_sql` → `ejecutar_lectura` (solo lectura, autorizador, límites).
   Si falla, hay un intento de corrección.
4. Redacción: `prompts.mensaje_respuesta` (≤ 50 filas) → respuesta directa.
5. La vista muestra la respuesta, los pasos, el SQL, los datos, la advertencia y las sugerencias.

---

## Guía de pruebas

```bash
pytest                               # suite completa (~460 pruebas, ~70 s); la red se bloquea siempre
pytest tests/services -q             # solo reglas de negocio (~10 s)
pytest tests/ai -q                   # solo IA
pytest tests/ui -q                   # solo interfaz (sin pantalla)
pytest -k "rollback" -v              # por nombre
python -m alquiler --autoprueba      # verificación de una instalación completa
```

**Aislamiento de red.** `tests/conftest.py` (fixture `sin_red`) bloquea `socket.connect` en toda
la suite. La API de Groq se reemplaza por `ClienteFalso` o por `httpx.MockTransport`; ninguna prueba lee un `alquiler.env` real (fixture `sin_archivo_env`).

| Archivo de pruebas | Qué verifica |
|---|---|
| `tests/test_config.py` | Valores por defecto, coma decimal, validación de cada variable y lectura de `alquiler.env` (BOM, CRLF, comillas, precedencia del entorno). |
| `tests/test_probar_ia.py` | `--probar-ia`: sin clave, OK, error de IA, respuesta inválida y la bandera en `main`. |
| `tests/test_db.py` | FK activas en SQLite y creación de la carpeta de la base. |
| `tests/test_models.py` | Restricciones de las 9 entidades (unicidad, CHECK, FK, JSON). |
| `tests/test_migraciones.py` | La migración Alembic es idéntica a los modelos e `init_db` es idempotente. |
| `tests/test_auth.py` | bcrypt, normalización del usuario, mensajes que no revelan usuarios y la matriz RBAC completa. |
| `tests/test_seed.py` | Datos demo: volumen, estados variados, determinismo y que alimentan a la IA. |
| `tests/test_aislamiento_red.py` | La red está bloqueada durante las pruebas. |
| `tests/test_documentacion.py` | Este índice está sincronizado con el código. |
| `tests/services/test_equipos.py` | Las 11 transiciones válidas y las 9 inválidas, CRUD y catálogo por rol. |
| `tests/services/test_clientes.py` | Edición por rol, baja (bloquea el usuario), historial y autorregistro (todo o nada, sin reclamar documentos existentes). |
| `tests/services/test_alquileres.py` | Costos, reservas, cancelación, pagos ≤ saldo y vencidos. |
| `tests/services/test_devoluciones.py` | Mora half-up, daños → correctivo y doble devolución rechazada. |
| `tests/services/test_mantenimiento.py` | Abrir y cerrar, equipo alquilado rechazado y rehabilitación. |
| `tests/services/test_reportes.py` | Ingresos, uso de flota (recortes al período) y morosidad. |
| `tests/services/test_usuarios.py` | Alta con RBAC, nadie se desactiva a sí mismo y contraseñas. |
| `tests/ai/test_demanda.py` | Pico de diciembre, confianza según el historial y rango nunca puntual. |
| `tests/ai/test_mantenimiento_ia.py` | El puntaje se desglosa y suma el total; persistencia sin duplicados. |
| `tests/ai/test_retrasos.py` | Suavizado, umbral de marcado y explicación. |
| `tests/ai/test_sql_seguro.py` | 18 rechazos (DML/DDL, `usuario`, `sqlite_master`, varias sentencias), sin falsos positivos, solo lectura, timeout, límite de tamaño y ruta con tildes. |
| `tests/ai/test_prompts.py` | El esquema inyectado excluye `usuario`; el prompt incluye la fecha y las reglas; esquemas JSON estrictos. |
| `tests/ai/test_llm.py` | Petición a Groq (modelo, `response_format` estricto), parseo, respuesta truncada, traducción de errores y reintentos (`httpx.MockTransport`). |
| `tests/ai/test_consultas.py` | Flujo en dos partes, aclaración, sin datos, corrección de SQL destructivo, errores y predefinidas. |
| `tests/ai/test_asistente.py` | Herramientas por rol, privacidad del cliente, uso de herramientas, permisos negados, límite de pasos, historial recortado, errores y preguntas rápidas. |
| `tests/ui/logica/test_contexto.py` | Rollback, sesión inválida, secciones por rol, formato y registro con entrada directa. |
| `tests/ui/logica/test_asistente_logica.py` | Turno de conversación como dict para la vista, sugerencias y respuesta rápida, y modo sin clave. |
| `tests/ui/logica/test_catalogo.py` | Lógica de equipos y mantenimiento. |
| `tests/ui/logica/test_personas.py` | Lógica de clientes, usuarios y perfil. |
| `tests/ui/logica/test_inicio.py` | Bloques por rol, conteos (vencidos frente a "vencen hoy"), ingresos del mes, base vacía, destinos visibles y que Inicio no persiste recomendaciones. |
| `tests/ui/test_arquitectura.py` | Las vistas no importan el backend (análisis AST). |
| `tests/ui/test_trabajador.py` | Trabajo fuera del hilo GUI, resultado en el GUI y dueño destruido. |
| `tests/ui/test_tokens.py` | `tokens.css` es la única fuente (también del styleguide, que no escribe colores y solo usa variables existentes): la paleta de la app sale de ahí, el lector ignora comentarios y `@media`, error claro si falta un token, el ejecutable lo empaqueta. |
| `tests/ui/test_tema.py` | Tema oscuro: contraste AA de todos los pares, componentes gráficos ≥ 3:1, Fusion y paleta oscura, emergentes oscuros y ningún color fuera de `tema.py`. |
| `tests/ui/test_iconos.py` | Un icono por sección, se dibuja y cambia de color al seleccionarse; el menú lateral los muestra. |
| `tests/ui/test_widgets_centro.py` | Fondo cósmico determinista, panel de vidrio, brillo neón, dona (segmentos, centro, vacía), tendencia (series, recarga sin acumular) y KPI con ícono. |
| `tests/ui/test_animacion.py` | Duraciones de los tokens, apagado sin pantalla y por variable, contador con formato, fundido que restaura el brillo, cascada, barras, temblor, brillo al pasar, fondo que flota, dona que gira y tendencia animada. |
| `tests/ui/test_portada.py` | Portada de ingreso: estructura, campos con ícono, login correcto, temblor ante error, entrada animada y crear cuenta de cliente. |
| `tests/ui/test_logo.py` | Geometría del cubo (8 vértices, 12 aristas, 3 ocultas), dibujo a varios tamaños, ícono de la aplicación, latido animado y uso en marca, portada y ventanas. |
| `tests/ui/test_widgets_inicio.py` | `TarjetaKPI` (clic navega solo con destino) y `BarraEstados` (segmentos, caso vacío, pintado). |
| `tests/ui/test_widgets.py` | Tabla, insignias, tarjeta de IA y configuración regional es-CO. |
| `tests/ui/test_ventana.py` | Login, barra lateral por rol, vistas perezosas y oferta de datos demo. |
| `tests/ui/test_vista_equipos.py` | Catálogo, panel de estados, diálogos, errores y mantenimiento. |
| `tests/ui/test_vistas_personas.py` | Clientes, usuarios y perfil. |
| `tests/ui/test_vistas_operaciones.py` | Alquiler, devolución, pago, reservas y doble clic. |
| `tests/ui/test_vista_reportes.py` | Generación en segundo plano y período inválido. |
| `tests/ui/test_vista_inicio.py` | Inicio como primera sección, tarjetas por rol, navegación por clic, recarga al volver y errores. |
| `tests/ui/test_vistas_ia.py` | Tarjetas, consola en dos partes, historial, doble Enter y cierre en curso. |
| `tests/ui/test_integracion.py` | Recorrido de los 3 roles, base vacía, rollback de punta a punta y cancelaciones. |
| `tests/ui/test_autoprueba.py` | `--autoprueba` y `--version`. |
