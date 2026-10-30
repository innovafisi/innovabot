# Bitácora de desarrollo — InnovaBot

> **Documento vivo**: registro operativo de la implementación del cambio OpenSpec `add-fisi-rag-chatbot`.
> Sigue la misma estructura que `docs/bitacora.md` (la memoria de planificación/infra); esta bitácora registra el *cómo se implementó*.
> Convención de actualización en la §10. La fuente de verdad de las tareas es `openspec/changes/add-fisi-rag-chatbot/tasks.md` (41 tareas en 7 grupos).

## Estado actual (2026-10-30, cierre de sesión D1)

- **Grupos 1–6 implementados**: 27/41 tareas de `tasks.md` marcadas como completas y verificadas. Las 14 restantes son: 5 pendientes por entorno (Docker/pgvector/Ollama/DevTools), 1 por el primer commit del equipo (gitleaks) y las 7 del grupo 7 (despliegue ECS, esperando indicaciones).
- Verificación final: backend `pytest` **106 passed, 4 skipped** (integración se salta sin entorno) + `ruff check .` limpio; frontend `npm run lint` 0 errores, `npm run test` 9/9, `npm run build` pasa; `ejemplo_contrato.py` y `uvicorn app.main:app` verificados en vivo (contrato exacto, 429 sin sesión, 403 webhook sin auth).
- Token de BotFather y API key de MaaS ya en `backend/.env` (gitignored): el grupo 6 se completó; el registro real del webhook es tarea 7.5.
- Sin comandos git: los commits los maneja exclusivamente el equipo.

## 1. La implementación en una mirada

Monorepo `backend/` + `frontend/` + `docker/` creado desde cero según `design.md`. El backend es un monolito modular FastAPI (`app/core`, `app/ingestion`, `app/guard`, `app/rag`, `app/interfaces`) con tres entrypoints (API web + webhook Telegram vía uvicorn; ingesta batch vía `python -m app.ingest`). El pipeline por mensaje va del chequeo más barato al más caro: longitud → rate limit → regex → light LM (guard+clasificación+reescritura en una llamada) → retrieval pgvector → LLM principal → validación anti-alucinación → respuesta con citas.

| Documento | Rol |
|---|---|
| `openspec/changes/add-fisi-rag-chatbot/tasks.md` | Fuente de verdad de las tareas y sus verificaciones |
| `backend/README.md` | Contrato del pipeline, ingesta y operación del backend |
| `docs/bitacora.md` | Memoria de planificación e infraestructura |
| `docs/bitacora-dev.md` | Este documento |

## 2. Decisiones de implementación (ADR-lite)

| # | Decisión | Alternativas descartadas | Por qué |
|---|---|---|---|
| 1 | `sentence-transformers` como dependencia opcional `[ingest]` con import perezoso en el cliente de embeddings | Instalarlo siempre | Torch pesa ~GBs; los unit tests mockean el cliente; solo la ingesta (y el contenedor de producción) lo necesitan |
| 2 | Tests de integración (pgvector, Ollama real) se saltan si no hay entorno (`TEST_DATABASE_URL` / `OLLAMA_BASE_URL` alcanzable), marcados como integración | Fallar si falta el entorno | La máquina local de desarrollo no tiene Docker/RDS; los tests corren donde exista el entorno |
| 3 | Consulta "fuera de alcance" → estado `bloqueada` con mensaje propio de alcance | Quinto estado | `web-ui`/design definen exactamente 4 estados (`ok\|bloqueada\|sin_resultados\|limitada`); no se inventan estados fuera de spec |
| 4 | Fallo doble de validación anti-alucinación → mensaje estándar con estado `sin_resultados` | Estado nuevo u `ok` sin citas | Es el estado más cercano semánticamente ("no hay información confiable disponible"); documentado en `backend/README.md` |
| 5 | Límites de uso aplicados en el orquestador (no en cada interfaz) | Cada interfaz llama a `core/limites` | El orquestador es la única pieza por la que pasan ambas interfaces; un solo lugar = imposible que una interfaz lo olvide |
| 6 | Hook de gitleaks versionado en `.githooks/` + `git config core.hooksPath .githooks` (lo ejecuta el equipo una vez) | Solo `.git/hooks/` local | `.git/` no se versiona; el repo es público y el hook debe distribuirse con el código |
| 7 | Tailwind CSS v3 con `tailwind.config.js` y tokens en `theme.extend.colors` | Tailwind v4 (`@theme` en CSS) | `AGENTS.md` exige literalmente tokens en `theme.extend.colors`; v3.4 es estable y conocido por el equipo |
| 8 | Boost de FAQs en retrieval por multiplicador de distancia (FAQ × factor < 1) | Re-ranking en Python o consulta separada | Es SQL común sobre pgvector, una sola consulta, cero código extra (KISS) |

## 3. Entorno de desarrollo y verificaciones

| Herramienta | Estado | Impacto |
|---|---|---|
| Python 3.14.7 | ✓ (`requires-python >=3.12`) | venv en `backend/.venv` |
| Node 24 / npm 11 | ✓ | scaffolding Vite + Tailwind + Vitest |
| Red a portales FISI/UNMSM | ✓ | scraper verificable en vivo |
| Docker | ✗ no instalado | Tareas 1.3 (`docker compose build`) y 1.5 (Ollama `/api/tags`) implementadas, verificación pendiente; tests de integración pgvector pendientes hasta haber BD de prueba |
| gitleaks | ✗ no instalado (ver §6) | Se intenta descargar el binario para verificar la tarea 1.6 |

## 4. Registro por grupos de tareas

### Grupo 1 — Scaffolding del monorepo

- [x] 1.1 `backend/` con `pyproject.toml`, paquete `app/`, ruff/pytest. Verificado: `pytest` en verde con test dummy.
- [x] 1.2 `frontend/` con Vite (React + TS), ESLint y Tailwind v3. Verificado: `npm run lint` y `npm run build` pasan. Nota: la plantilla actual de Vite trae oxlint y TypeScript 7; se sustituyó oxlint por ESLint (requisito de la tarea) y se fijó TypeScript 5.9 (typescript-eslint aún no soporta TS 7).
- [ ] 1.3 `docker/` (Dockerfile.backend, Dockerfile.frontend, docker-compose.yml con app+ollama+ingest). **Verificación pendiente**: `docker compose build` requiere Docker (no instalado en la máquina de desarrollo).
- [x] 1.4 Settings tipado por env vars (`app/core/settings.py` + `backend/.env.example`). Verificado: test que la app falla con mensaje claro en español listando las variables que faltan.
- [ ] 1.5 Ollama en compose de desarrollo (`OLLAMA_NUM_PARALLEL=1`, volumen persistente, 11434 solo en 127.0.0.1) + `scripts/descargar_modelo.sh`. **Verificación pendiente**: `GET /api/tags` requiere Docker/Ollama.
- [ ] 1.6 gitleaks: `.gitleaks.toml` (extiende el ruleset por defecto) + hook `.githooks/pre-commit` (instalable con `git config core.hooksPath .githooks`). Verificado con el binario 8.30.1: detecta un secreto falso de entropía alta (exit 1) y el escaneo del contenido del repo pasa limpio (exit 0). **Pendiente**: la pasada a nivel de commit la ejecuta el equipo con su primer commit (la herramienta de desarrollo no tiene permisos de git). Nota: gitleaks detectó que `backend/.env` ya contiene credenciales reales — correcto, está en `.gitignore` y el hook solo escanea lo staged.

### Grupo 2 — Ingesta de conocimiento (subagente)

- [x] 2.1 Scraper de noticias del portal FISI (`app/ingestion/noticias.py`, selectores centralizados en `SELECTORES`). Verificado: test contra HTML fixture + **ejecución real** que extrajo 3 noticias con título/contenido/URL correctos y registró un fallo TLS sin detenerse (ver §7).
- [x] 2.2 PDFs con pdfplumber (`pdfs.py`): descarga, extracción, chunking por secciones (ventanas ~800 chars, solapamiento 200), `PdfIlegible` registrado y excluido. Verificado con fixtures (PDF válido de 3 secciones generado programáticamente + PDF ilegible sin texto).
- [x] 2.3 FAQs curadas (`faqs.py`): parser `## ¿Pregunta?` → fragmento `tipo=faq`; `data/faqs.md` con 8 Q&As reales. Verificado: cada Q&A genera fragmento; re-ejecutar no duplica (mismo hash).
- [x] 2.4 Portal central UNMSM (`portal.py`): solo se ingieren las secciones del YAML (`data/secciones_portal.yml`, 3 secciones verificadas con contenido real). Verificado con fixture.
- [x] 2.5 Deduplicación (`chunking.py`): SHA-256 del contenido normalizado como id; versión actualizada marca obsoleta la anterior por URL. Verificado: re-ingesta sin cambios no inserta; documento actualizado reemplaza.
- [ ] 2.6 Embeddings + indexación pgvector (`indexar.py`): implementado (upsert, `marcar_obsoletos`, metadata obligatoria, validación de metadata incompleta). **Verificación pendiente**: test de integración escrito (`tests/integration/test_indexar_pgvector.py`) pero sin Docker/RDS ni extra `[ingest]` en esta máquina.
- [x] 2.7 `backend/README.md`: ejecución de la ingesta, variables, formato YAML/Markdown, tests de integración. Verificado: los comandos documentados corren tal cual (componentes verificados por separado; la ingesta completa real es tarea 7.4 en el ECS).
- Hallazgos del scraper real: el portal FISI **no publica fecha de publicación** en el HTML (la fecha queda None salvo marcado estructurado o texto explícito "publicado el…"); el feed RSS del portal devuelve error; unmsm.edu.pe también tiene problemas de certificado para clientes no-Windows.

### Grupo 3 — Guardián de entrada

- [x] 3.1 `app/guard/regex_guard.py`: 8 patrones anclaados (override ES/EN, revelar system prompt, jailbreak) con motivo descriptivo para auditoría. Verificado: 15 inyecciones canónicas bloqueadas, 7 consultas legítimas con palabras sospechosas aisladas pasan.
- [ ] 3.2 `app/guard/light_lm_guard.py`: llamada combinada guard+clasificación+reescritura (JSON `{safe, category, rewritten_query}`, temperatura 0, `format: json` de Ollama). **Parte unitaria verificada** con mock (instrucción encubierta → insegura; académica → segura+clasificada; salida incompleta → conservadora). **Pendiente**: prueba de integración contra Ollama real (`tests/integration/test_light_lm_real.py`, se salta sin Ollama).
- [x] 3.3 `app/guard/mensajes.py` + derivación temprana en el orquestador. Verificado: consulta bloqueada no genera llamadas al LLM principal ni al almacén vectorial; fuera de alcance responde temas sin tocar retrieval.
- [x] 3.4 Registro de bloqueos (`app/core/logs.py::registrar_bloqueo`). Verificado: cada bloqueo deja exactamente un registro JSON con motivo, timestamp e interfaz.

### Grupo 4 — Pipeline de respuesta RAG

- [ ] 4.1 `app/rag/retrieval.py`: top-k con boost de FAQs (×0.8 sobre distancia coseno) y umbral de similitud mínima. **Pendiente**: test de integración con pgvector (`tests/integration/test_retrieval_pgvector.py`, requiere `TEST_DATABASE_URL` + extra `[ingest]`).
- [x] 4.2 `app/rag/generacion.py`: system prompt restrictivo (solo fragmentos, español, sin inventar, sin revelar instrucciones), temperatura baja en `ClienteLLMPrincipal`. Verificado con mock: el prompt incluye exclusivamente los fragmentos + instrucción de citar fuentes.
- [x] 4.3 `app/rag/validacion.py` + política de reintento en el orquestador. Verificado con mocks: respuesta no respaldada no se entrega tal cual (1 regeneración con feedback; a la segunda falla, mensaje estándar); respaldada se entrega sin cambios.
- [x] 4.4 Ensamblado de citas deduplicadas por URL + mensaje estándar sin resultados. Verificado: test end-to-end del pipeline con mocks (estados ok/bloqueada/sin_resultados, citas correctas).
- [ ] 4.5 Ejemplo ejecutable `backend/ejemplo_contrato.py` verificado (imprime el contrato exacto en los 4 estados). **Pendiente**: sección del contrato en `backend/README.md` (espera a que el subagente de ingesta cree el README para no pisarlo).
- [x] 4.6 `app/core/limites.py` (verificado en grupo 1, ver arriba).
- [x] 4.7 Log estructurado por consulta recibida (`{interfaz, categoria, estado, latencia_ms, timestamp}`). Verificado: consulta ok y bloqueada dejan cada una su registro con el estado correcto; la bloqueada por regex queda sin categoría (nunca clasificada).

### Grupo 5 — API web y frontend React

- [x] 5.1 `app/interfaces/api.py` + `app/main.py`: `POST /api/chat` con validación de entrada, formato `{reply, citas, estado}`, 429 con estado `limitada` (sin session ID o límite excedido), CORS por `CORS_ORIGINS`, identidad `web:<X-Session-ID>`. Verificado con 8 tests de API (formato completo, bloqueada, 429×2, 422, CORS permitido/ajeno).
- [x] 5.2 SPA React (subagente): dos vistas fiel al prototipo `index-lima.html`, hilo con typing, citas, modo prototipo sin backend. Verificado: `npm run lint` 0 errores, `npm run build` pasa, prueba manual documentada en `frontend/README.md`.
- [ ] 5.3 Identidad visual + tema claro/oscuro + responsive (subagente): **implementada** (tokens Tailwind, banda/huaca/greca Lima, avatar sobre blanco fijo, toggle persistente, máx 720px). **Verificación pendiente**: revisión en viewport móvil con DevTools (procedimiento documentado en `frontend/README.md` para el equipo).
- [x] 5.4 Estados de la UI (bloqueada, limitada 200/429, sin_resultados, fallo de red) con mensajes amigables. Verificado: tests de componentes renderizan cada estado.
- [x] 5.5 Session ID anónima (UUID v4 en localStorage, header `X-Session-ID`) + contador N/500 con aviso al ≥90%. Verificado: tests de componentes (persistencia entre remount, aviso a 450/500).
- Desviaciones menores documentadas por el subagente: neutrales del prototipo mapeados a la paleta slate de Tailwind (casi idénticos); token añadido `terracota.claro` para el crédito en oscuro; botón de envío deshabilitado mientras llega la respuesta (el spec permite ambos).

### Grupo 6 — Bot de Telegram

El equipo confirmó que el token de BotFather ya está en `backend/.env` (junto a la API key de MaaS); se implementó el grupo completo con mocks del API de Telegram.

- [x] 6.1 `app/interfaces/telegram.py`: `POST /telegram/webhook/{token}` con doble verificación (token en ruta + header `X-Telegram-Bot-Api-Secret-Token`). Verificado: autenticada se procesa; secret equivocado → 401; token equivocado → 403.
- [x] 6.2 Flujo consulta → orquestador (el mismo que la web) → respuesta con citas en el mismo chat; identidad `telegram:<user_id>`; límites y longitud los aplica el orquestador. Verificado con mock de la API de Telegram: un update legítimo → exactamente una respuesta al chat de origen; 6ª consulta del minuto → mensaje de límite; 501 chars → aviso de acortar.
- [x] 6.3 `/start` (bienvenida con ejemplos) y `/help` (temas + comandos). Verificado: cada comando responde su mensaje y NO entra al pipeline (ni consume rate limit).
- [x] 6.4 Mensaje amigable ante fallo del pipeline + `logger.exception` para el equipo. Verificado: pipeline que lanza excepción → usuario recibe el mensaje amigable, Telegram recibe 200, queda exactamente un log de error.
- [x] 6.5 Filtro de chats privados ANTES del pipeline. Verificado: update de grupo → sin respuesta, sin pipeline, sin consumo; 10 mensajes de grupo no consumen el cupo del usuario privado; update privado se procesa con normalidad.
- Detalle de implementación: el campo `from` de Telegram es un objeto User (no un int) — modelo `UsuarioTelegram` con alias; si faltara `from`, la identidad cae al `chat.id` (chats privados coinciden).

### Grupo 7 — Despliegue en Huawei Cloud

Esperando indicaciones del equipo (bitacora §Pendientes).

## 5. Estructura de código creada

```
backend/
├── pyproject.toml          # deps + ruff + pytest
├── README.md               # contrato del pipeline, ingesta, operación
├── .env.example            # plantilla de variables de entorno (sin valores reales)
├── app/
│   ├── core/               # settings, modelos, clientes (MaaS/Ollama/RDS/Telegram), límites, logs
│   ├── ingestion/          # scraper noticias, pdfs, faqs, portal central, chunking, indexación
│   ├── guard/              # regex + light LM (guardián, clasificación)
│   ├── rag/                # reescritura, retrieval, generación, validación, orquestador
│   └── interfaces/         # api web (/api/chat) + webhook Telegram
└── tests/                  # unit/ + integration/ + fixtures/
frontend/                   # React + TS + Vite + Tailwind v3 + Vitest
docker/                     # Dockerfiles + docker-compose (dev y producción)
```

## 6. Seguridad del repo durante el desarrollo

- Ninguna credencial en código: todo por variables de entorno (`app/core/settings.py`), plantilla `.env.example` sin valores reales.
- `.gitignore` ya cubre `.env*`, `*.pem`, `*.key`, `secrets/`.
- Gitleaks: configuración `.gitleaks.toml` + hook `.githooks/pre-commit` (instalable con `git config core.hooksPath .githooks`). Verificación de detección: ver §4 grupo 1.
- Los commits los maneja exclusivamente el equipo (la herramienta de desarrollo no ejecuta comandos git).

## 7. Incidentes y desvíos

| # | Incidente | Causa | Solución |
|---|---|---|---|
| 1 | La primera ejecución real del scraper falló con `CERTIFICATE_VERIFY_FAILED` contra sistemas.unmsm.edu.pe | El portal FISI sirve una **cadena TLS incompleta**: envía un intermedio Sectigo equivocado y el correcto solo se resuelve por AIA (Windows lo hace automáticamente; Linux/Python no) | Se incluye el intermedio público correcto en el repo (`app/ingestion/intermedio_sectigo.crt`, descargado del AIA) y el cliente HTTP construye el contexto SSL con certifi + ese CRT. Verificación TLS estricta, nunca deshabilitada. Necesario también en el ECS Linux. Nota: se renombró de `.pem` a `.crt` porque `.gitignore` excluye `*.pem` (regla para claves privadas) y el archivo público debía poder commitearse |
| 2 | Una primera versión del scraper cogía cualquier fecha del cuerpo de la noticia como fecha de publicación | El portal no publica fecha estructurada; textos como "hasta el 01 de noviembre" daban metadata falsa | La fecha solo se acepta de marcado estructurado (`time[datetime]`, itemprop) o de texto que dice explícitamente "publicado el DD de mes de YYYY"; si no, queda None (es opcional) |

## 8. Lecciones

- **`*.pem` en `.gitignore` pilla también certificados PÚBLICOS**: usar extensión `.crt`/`.cer` para material público de CA y reservar `.pem` para claves.
- **"Connection refused" vs timeout** (ya documentado en bitacora §4.6) y ahora **cadena TLS incompleta**: los portales UNMSM tienen rarezas de infraestructura; el scraper debe registrar fallos por página sin detenerse — el spec ya lo exigía y sirvió de red de seguridad real.
- Los subagentes en paralelo funcionan bien con alcances disjuntos (ingesta vs frontend vs pipeline central) y `tasks.md` como tablero compartido de checkboxes; el único roce fue ruff señalando archivos ajenos a mitad de ejecución, que cada dueño corrigió en su alcance.

## 9. Cronología de sesiones de desarrollo

| Fecha | Sesión | Hitos |
|---|---|---|
| 2026-10-30 | **D1 — Implementación grupos 1–6** | Conciliación 39/40→41 tareas · scaffolding backend+frontend+docker+gitleaks · settings tipado · ingesta completa con scraper real (hallazgo TLS del portal FISI, §7) · guardián regex+light LM · pipeline RAG con orquestador único · API web + SPA React con arte Lima · bot de Telegram completo · 27/41 tareas verificadas (106 tests backend + 9 frontend en verde) · pendientes: verificaciones con Docker/pgvector/Ollama, DevTools 5.3, primer commit (gitleaks) y grupo 7 |

## 10. Convención para actualizar esta bitácora

1. **Al cerrar cada sesión**: agregar fila a §9 y reescribir "Estado actual".
2. **Por grupo de tareas** (§4): marcar cada tarea con `[x]` solo cuando su verificación de `tasks.md` pasó; si la verificación no pudo ejecutarse en este entorno, dejar `[ ]` con nota *verificación pendiente* y cómo ejecutarla.
3. **Decisiones de implementación** nuevas: fila en §2, numeración consecutiva.
4. **Incidentes/desvíos** (§7): causa y solución; **lecciones** (§8) si aplica a futuro.
5. No borrar historia; las correcciones se añaden junto al original.

## Pendientes

- [ ] Verificar 1.3 y 1.5 con Docker (local con Docker Desktop o en el ECS).
- [ ] Tests de integración pgvector (2.6, 4.1) con `TEST_DATABASE_URL` + extra `[ingest]` (instrucciones en `backend/README.md`).
- [ ] Prueba de integración contra Ollama real (3.2) cuando exista entorno.
- [ ] Revisión en viewport móvil con DevTools (5.3) — procedimiento en `frontend/README.md`.
- [ ] Primer commit del equipo con el hook de gitleaks activo (`git config core.hooksPath .githooks`) → cierra 1.6.
- [ ] Grupo 7 (despliegue ECS): esperando indicaciones del equipo; el token de BotFather y la API key de MaaS ya están en `backend/.env`.
