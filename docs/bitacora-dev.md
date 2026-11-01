# Bitácora de desarrollo — InnovaBot

> **Documento vivo**: registro operativo de la implementación del cambio OpenSpec `add-fisi-rag-chatbot`.
> Sigue la misma estructura que `docs/bitacora.md` (la memoria de planificación/infra); esta bitácora registra el *cómo se implementó*.
> Convención de actualización en la §10. La fuente de verdad de las tareas es `openspec/changes/add-fisi-rag-chatbot/tasks.md` (41 tareas en 7 grupos).

## Estado actual (2026-10-31, cierre de sesión D4)

- **Grupo 7 desplegado en el ECS (39/41 tareas)**: stack prod Up (app + ollama + caddy) con TLS Let's Encrypt, modelo light LM verificado por digest, **primera ingesta: 242 fragmentos**, webhook de Telegram registrado (`getWebhookInfo` limpio) y cron semanal instalado. Pendientes: **7.5** (prueba end-to-end con mensaje real + rotar el token del bot) y **7.6** (Vercel, requiere la cuenta del equipo).
- **Cambio `reduce-validation-latency` aplicado y verificado**: validación con contexto acotado (3 fragmentos × 600 chars) → **latencia en caliente ~11 s** (antes 32–40 s, −70%).
- **`harden-llm-security` completo (20/20)**: la 6.3 (digests vía `docker compose config`) se verificó en el ECS.
- Verificación D4: 150 tests unitarios + ruff limpio (local); `/api/chat` end-to-end `estado: ok` en producción con citas.
- **ECS**: flavor migrado a `c7n.xlarge.2` (AVX expuesto — incidente §7.8); acceso SSH por clave desde la laptop del equipo; **login root por password aún activo** (rotar y volver a `PasswordAuthentication no`).
- **Pendiente del equipo**: commit/push de los fixes de despliegue (`backend/app/ingest.py`, `COPY backend/data`, compose con `hf-cache`/`OLLAMA_NUM_THREADS`, lock regenerado con 3.12, guía §5/§12), Vercel (7.6), E2E Telegram + rotación de token (7.5), rotar password root.
- Hook de gitleaks: mecanismo único versionado en `.githooks/` — **el equipo debe ejecutar `git config core.hooksPath .githooks` una vez** antes del próximo commit.
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

## 3. Entorno de desarrollo: herramientas, scripts y comandos

| Herramienta | Estado | Impacto |
|---|---|---|
| Python 3.14.7 | ✓ (`requires-python >=3.12`) | venv en `backend/.venv` |
| Node 24 / npm 11 | ✓ | scaffolding Vite + Tailwind + Vitest |
| Red a portales FISI/UNMSM | ✓ | scraper verificable en vivo |
| Docker Desktop | ✓ (instalado en D2 vía winget, engine 29.9.2) | Tareas 1.3 y 1.5 verificadas; contenedores de prueba pgvector + Ollama |
| gitleaks | ✓ 8.30.1 (instalado en D2 vía winget) | Tarea 1.6 verificada; hook pre-commit |
| sentence-transformers + torch | ✓ (extra `[ingest]` en el venv, D2) | Embeddings reales en tests de integración |

### 3.1 Scripts y comandos del entorno (instalación, D2)

Instalaciones (con permiso del equipo, de preferencia winget):

```powershell
# gitleaks (ojo: el ID es case-sensitive)
winget install -e --id Gitleaks.Gitleaks --accept-source-agreements --accept-package-agreements --silent

# Docker Desktop (WSL2 ya estaba habilitado; requiere arrancar la app tras instalar)
winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

Extra de ingesta en el venv (arrastra torch; en Windows PyPI sirve torch CPU ~200 MB):

```powershell
cd backend
.venv/Scripts/pip.exe install ".[ingest]"
```

**Gotcha de Docker en shells nuevos**: al llamar a `docker` fuera de la app, falla con
`docker-credential-desktop: executable file not found in %PATH%`. Fix: prependear el bin dir:

```powershell
$env:PATH = "C:\Program Files\Docker\Docker\resources\bin;$env:PATH"
```

### 3.2 Contenedores de prueba (pgvector + Ollama)

```powershell
# PostgreSQL 18 con pgvector para los tests de integración (tareas 2.6 y 4.1)
docker run -d --name pgvector-test -e POSTGRES_PASSWORD=test -p 5432:5432 pgvector/pgvector:pg18
docker exec pgvector-test pg_isready -U postgres   # esperarlo antes de correr los tests

# Ollama + light LM (tarea 1.5): el script oficial del repo hace up + pull + verificación
bash scripts/descargar_modelo.sh   # termina con "OK: el modelo aparece en /api/tags"
```

### 3.3 Comandos de verificación

```powershell
# Backend: unit + integración (integración requiere TEST_DATABASE_URL; sin él se salta limpio)
cd backend
$env:TEST_DATABASE_URL = "postgresql://postgres:test@localhost:5432/postgres"
.venv/Scripts/python.exe -m pytest tests -q          # 110 passed
.venv/Scripts/python.exe -m ruff check .

# Frontend
cd frontend
npm run lint ; npm run test -- --run ; npm run build

# Docker: build de las imágenes (tarea 1.3)
docker compose -f docker/docker-compose.yml build

# gitleaks: escaneo manual del árbol (sin git)
gitleaks detect --source . --no-git --redact
```

### 3.4 Verificación visual de la UI (tarea 5.3, Playwright)

Playwright no está en el proyecto (no contamina `package.json`): se instala en un dir temporal
y un script toma las capturas en viewport móvil 390px, alterna el tema en ambas vistas y
comprueba scroll horizontal + errores de consola:

```powershell
$dir = "$env:TEMP\innovabot-visual"; New-Item -ItemType Directory -Force $dir | Out-Null
cd $dir; npm init -y | Out-Null; npm install playwright; npx playwright install chromium
# script verificar.mjs: nav → screenshots (landing/chat × claro/oscuro) → toggle → scrollWidth check
node verificar.mjs http://localhost:5173   # con `npm run dev` corriendo en frontend/
```

Resultado D2: `SCROLL_CHAT/LANDING {"scrollWidth":390,"innerWidth":390}`, `CONSOLE_ERRORS []`,
4 capturas revisadas — tokens correctos en ambos temas, logo de huaca visible sobre blanco fijo.

## 4. Registro por grupos de tareas

### Grupo 1 — Scaffolding del monorepo

- [x] 1.1 `backend/` con `pyproject.toml`, paquete `app/`, ruff/pytest. Verificado: `pytest` en verde con test dummy.
- [x] 1.2 `frontend/` con Vite (React + TS), ESLint y Tailwind v3. Verificado: `npm run lint` y `npm run build` pasan. Nota: la plantilla actual de Vite trae oxlint y TypeScript 7; se sustituyó oxlint por ESLint (requisito de la tarea) y se fijó TypeScript 5.9 (typescript-eslint aún no soporta TS 7).
- [x] 1.3 `docker/` (Dockerfile.backend, Dockerfile.frontend, docker-compose.yml con app+ollama+ingest). **Verificado en D2**: `docker compose build` completo tras corregir el Dockerfile (torch CPU-first, ver §7.3) — build de ~1h a ~1min.
- [x] 1.4 Settings tipado por env vars (`app/core/settings.py` + `backend/.env.example`). Verificado: test que la app falla con mensaje claro en español listando las variables que faltan.
- [x] 1.5 Ollama en compose de desarrollo (`OLLAMA_NUM_PARALLEL=1`, volumen persistente, 11434 solo en 127.0.0.1) + `scripts/descargar_modelo.sh`. **Verificado en D2**: script ejecutado (pull de 1.9 GB) — termina con "OK: el modelo aparece en /api/tags".
- [x] 1.6 gitleaks: `.gitleaks.toml` (extiende el ruleset por defecto, allowlist de tests y `.venv`) + hook `.githooks/pre-commit` (instalable con `git config core.hooksPath .githooks`). **Verificado en D2** con el binario 8.30.1 (winget): detecta un secreto sintético realista (exit 1; ojo: las claves de documentación tipo `AKIAIOSFODNN7EXAMPLE` están en los stopwords por defecto y NO cuentan como prueba) y el contenido commiteable del repo escanea limpio (exit 0). `backend/.env` (credenciales reales en disco) NO está allowlisted a propósito: gitleaks lo señala en escaneos completos — correcto; no llega al repo (.gitignore + hook staged-only). **D2 concilió el mecanismo de hook al único versionado `.githooks/`** (ADR §2.6): se eliminaron un hook directo en `.git/hooks/` y un `.pre-commit-config.yaml` duplicados. **Pendiente del equipo**: `git config core.hooksPath .githooks` (una vez por clon).

### Grupo 2 — Ingesta de conocimiento (subagente)

- [x] 2.1 Scraper de noticias del portal FISI (`app/ingestion/noticias.py`, selectores centralizados en `SELECTORES`). Verificado: test contra HTML fixture + **ejecución real** que extrajo 3 noticias con título/contenido/URL correctos y registró un fallo TLS sin detenerse (ver §7).
- [x] 2.2 PDFs con pdfplumber (`pdfs.py`): descarga, extracción, chunking por secciones (ventanas ~800 chars, solapamiento 200), `PdfIlegible` registrado y excluido. Verificado con fixtures (PDF válido de 3 secciones generado programáticamente + PDF ilegible sin texto).
- [x] 2.3 FAQs curadas (`faqs.py`): parser `## ¿Pregunta?` → fragmento `tipo=faq`; `data/faqs.md` con 8 Q&As reales. Verificado: cada Q&A genera fragmento; re-ejecutar no duplica (mismo hash).
- [x] 2.4 Portal central UNMSM (`portal.py`): solo se ingieren las secciones del YAML (`data/secciones_portal.yml`, 3 secciones verificadas con contenido real). Verificado con fixture.
- [x] 2.5 Deduplicación (`chunking.py`): SHA-256 del contenido normalizado como id; versión actualizada marca obsoleta la anterior por URL. Verificado: re-ingesta sin cambios no inserta; documento actualizado reemplaza.
- [x] 2.6 Embeddings + indexación pgvector (`indexar.py`): implementado (upsert, `marcar_obsoletos`, metadata obligatoria, validación de metadata incompleta). **Verificado en D2** contra `pgvector/pgvector:pg18` real con embeddings e5 reales: fragmento indexado recuperable por búsqueda semántica y filtrable por metadata. El test cazó el bug del cast `::vector` (§7.3).
- [x] 2.7 `backend/README.md`: ejecución de la ingesta, variables, formato YAML/Markdown, tests de integración. Verificado: los comandos documentados corren tal cual (componentes verificados por separado; la ingesta completa real es tarea 7.4 en el ECS).
- Hallazgos del scraper real: el portal FISI **no publica fecha de publicación** en el HTML (la fecha queda None salvo marcado estructurado o texto explícito "publicado el…"); el feed RSS del portal devuelve error; unmsm.edu.pe también tiene problemas de certificado para clientes no-Windows.

### Grupo 3 — Guardián de entrada

- [x] 3.1 `app/guard/regex_guard.py`: 8 patrones anclaados (override ES/EN, revelar system prompt, jailbreak) con motivo descriptivo para auditoría. Verificado: 15 inyecciones canónicas bloqueadas, 7 consultas legítimas con palabras sospechosas aisladas pasan.
- [x] 3.2 `app/guard/light_lm_guard.py`: llamada combinada guard+clasificación+reescritura (JSON `{safe, category, rewritten_query}`, temperatura 0, `format: json` de Ollama). **Parte unitaria verificada** con mock (instrucción encubierta → insegura; académica → segura+clasificada; salida incompleta → conservadora). **Verificado en D2 contra Ollama real**: JSON parseable con las tres claves en 8.8s — tras el fix de threads en CPU híbrido (§7.3), que bajó la generación de 0.17 tok/s a velocidad normal.
- [x] 3.3 `app/guard/mensajes.py` + derivación temprana en el orquestador. Verificado: consulta bloqueada no genera llamadas al LLM principal ni al almacén vectorial; fuera de alcance responde temas sin tocar retrieval.
- [x] 3.4 Registro de bloqueos (`app/core/logs.py::registrar_bloqueo`). Verificado: cada bloqueo deja exactamente un registro JSON con motivo, timestamp e interfaz.

### Grupo 4 — Pipeline de respuesta RAG

- [x] 4.1 `app/rag/retrieval.py`: top-k con boost de FAQs (×0.8 sobre distancia coseno) y umbral de similitud mínima. **Verificado en D2** contra pgvector real: la FAQ correspondiente se recupera con prioridad y la metadata es filtrable por SQL.
- [x] 4.2 `app/rag/generacion.py`: system prompt restrictivo (solo fragmentos, español, sin inventar, sin revelar instrucciones), temperatura baja en `ClienteLLMPrincipal`. Verificado con mock: el prompt incluye exclusivamente los fragmentos + instrucción de citar fuentes.
- [x] 4.3 `app/rag/validacion.py` + política de reintento en el orquestador. Verificado con mocks: respuesta no respaldada no se entrega tal cual (1 regeneración con feedback; a la segunda falla, mensaje estándar); respaldada se entrega sin cambios.
- [x] 4.4 Ensamblado de citas deduplicadas por URL + mensaje estándar sin resultados. Verificado: test end-to-end del pipeline con mocks (estados ok/bloqueada/sin_resultados, citas correctas).
- [x] 4.5 Ejemplo ejecutable `backend/ejemplo_contrato.py` verificado (imprime el contrato exacto en los 4 estados) + sección `## Pipeline de respuesta (contrato)` en `backend/README.md` (entrada/salida/estados). Verificado: el ejemplo imprime los 4 estados y los comandos del README corren tal cual (tasks.md 4.5 `[x]`).
- [x] 4.6 `app/core/limites.py` (verificado en grupo 1, ver arriba).
- [x] 4.7 Log estructurado por consulta recibida (`{interfaz, categoria, estado, latencia_ms, timestamp}`). Verificado: consulta ok y bloqueada dejan cada una su registro con el estado correcto; la bloqueada por regex queda sin categoría (nunca clasificada).

### Grupo 5 — API web y frontend React

- [x] 5.1 `app/interfaces/api.py` + `app/main.py`: `POST /api/chat` con validación de entrada, formato `{reply, citas, estado}`, 429 con estado `limitada` (sin session ID o límite excedido), CORS por `CORS_ORIGINS`, identidad `web:<X-Session-ID>`. Verificado con 8 tests de API (formato completo, bloqueada, 429×2, 422, CORS permitido/ajeno).
- [x] 5.2 SPA React (subagente): dos vistas fiel al prototipo `index-lima.html`, hilo con typing, citas, modo prototipo sin backend. Verificado: `npm run lint` 0 errores, `npm run build` pasa, prueba manual documentada en `frontend/README.md`.
- [x] 5.3 Identidad visual + tema claro/oscuro + responsive (subagente): **implementada** (tokens Tailwind, banda/huaca/greca Lima, avatar sobre blanco fijo, toggle persistente, máx 720px). **Verificada en D2** con Playwright en viewport móvil 390px (§3.4): 4 capturas revisadas (landing/chat × claro/oscuro), colores y motivos según tokens en ambos temas, logo visible en claro y oscuro, toggle alterna ambas vistas, sin scroll horizontal, 0 errores de consola.
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

### Grupo 7 — Despliegue en Huawei Cloud (D4)

Desplegado y verificado en el ECS `ecs-innovabot` (flavor `c7n.xlarge.2`), operando por SSH:

- [x] 7.1 Stack prod Up (app + ollama + caddy); `/docs` responde vía Caddy con TLS.
- [x] 7.2 Cert Let's Encrypt emitido por Caddy contra `innovabot.duckdns.org`; SG verificado en S1.
- [x] 7.3 Modelo `qwen2.5:3b-instruct-q4_K_M` en volumen persistente; digest `161ddde4…` verificado con `ollama list` (el `pull` no acepta `@sha256`, §7.12); guardián JSON válido en ~5 s.
- [x] 7.4 Tablas + índice HNSW creados por la ingesta idempotente; **242 fragmentos** (portal 209, faq 8, noticia 6). PDFs aportaron 0: el único enlace del portal es un PDF escaneado (ilegible), registrado y excluido según spec — procesar más páginas de PDFs queda como mejora del contenido.
- [ ] 7.5 Webhook registrado y limpio; **falta**: mensaje real end-to-end y **rotar el token** en BotFather (el actual viajó en URLs antes de la ruta fija).
- [ ] 7.6 Vercel: pendiente del equipo (root `frontend/`, `VITE_API_URL`, luego ajustar `CORS_ORIGINS`).
- [x] 7.7 Comandos de `docs/guia-deploy.md` ejecutados tal cual; los desvíos encontrados quedaron corregidos en guía y repo (§7.9–7.13).

Cambio `reduce-validation-latency` (D4): validación acotada (3 fragmentos × 600 chars, `app/rag/validacion.py`) → latencia en caliente **10.7–10.9 s** (antes 32–40 s). En el límite del objetivo <10 s; si se requiere bajar más: recortar más el contexto (riesgo de falsos "sin respaldo"), light LM más pequeño o más vCPU.

### Cambio `harden-llm-security` (D3) — hardening OWASP Top 10 LLM

Aplicado en D3 con **5 subagentes en paralelo** de alcances disjuntos (pipeline/guardián, core/interfaces, ingesta, frontend, cadena de suministro) sobre una base compartida creada antes del reparto (campos de settings, `mensajes.ERROR_SERVICIO`, `guard/fuga.py`). 19/20 tareas verificadas.

- [x] 1.1–1.3 (agente A): delimitadores `<<<FRAGMENTO n>>> … <<<FIN>>>` + instrucción anti-inyección en generación y validación; guardián fail-closed (reescritura vacía o demasiado larga → consulta original); canario por proceso (`app/guard/fuga.py`) y bloqueo de respuestas que lo contengan (motivo `fuga_system_prompt`).
- [x] 2.1–2.2 (A + B): marcador `{"fuentes": [n]}` al final de la respuesta → citas solo de los fragmentos usados (fallback: todas, nunca se pierden); `LLM_MAX_TOKENS`/`LLM_TIMEOUT_SECONDS` en `ClienteLLMPrincipal`; fallo del LLM → `ERROR_SERVICIO` con estado `sin_resultados` y log con solo el tipo de excepción.
- [x] 3.1–3.2 (B): `verificar_ip` (X-Forwarded-For de Caddy) en la API web — deliberadamente NO en el orquestador: las peticiones de Telegram llegan desde IPs compartidas por todos los usuarios; purga de contadores con `TOPE_IDENTIDADES=10_000` + TTL 1 h.
- [x] 4.1–4.3 (B): ruta fija `POST /telegram/webhook` (el token ya no viaja en la URL; auth solo por header secreto; **rotar el token al desplegar**); redacción de logs (sin cuerpos de respuesta ni DSN); `RegistroUpdates` anti-replay por `update_id` (TTL 1 h, marca tras procesar con éxito).
- [x] 5.1–5.2 (C): allowlist anti-SSRF en PDFs (`sistemas.unmsm.edu.pe`, `unmsm.edu.pe` + `INGESTA_HOSTS_PERMITIDOS`; rechazo de hosts que resuelvan a IP privada/loopback/link-local; verificación de cabecera `%PDF-`).
- [x] 6.1/6.2/6.4 (E + coordinador): `requirements.lock` con hashes (42 paquetes; el extra `[ingest]` queda fuera por torch plataforma-específico); `EMBEDDINGS_REVISION` cableada en `ClienteEmbeddings` (revisión real `614241f…` de Hugging Face); digests del modelo de Ollama y de las imágenes (python/ollama/caddy) fijados en docker; `pip-audit` sin CVEs; SBOM documentado en `backend/README.md`.
- [ ] 6.3: digests aplicados en `Dockerfile.backend` y `docker-compose.prod.yml`; verificación con `docker compose config` pendiente (sin Docker CLI en esta máquina — correr en el ECS).
- [x] 7.1 (D): `esUrlSegura` en la web — solo `http/https` se renderiza como enlace; otro esquema, texto sin `href`.
- [x] 8.1–8.3: `.env.example`, `backend/README.md` (contrato + cadena de suministro) y `docs/guia-deploy.md` (variables nuevas, webhook sin token, digest de Ollama) actualizados; suite completa en verde. `TELEGRAM_WEBHOOK_PATH` descopeado por KISS (ruta fija suficiente).

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
| 3 | El build de Docker tardaba ~1h y fallaba; `pip install ".[ingest]"` descargaba ~4 GB de paquetes `nvidia-*` | En Linux, PyPI sirve **torch CUDA** por defecto — y el proyecto es CPU-only por diseño (ECS sin GPU) | `Dockerfile.backend`: `pip install torch --index-url https://download.pytorch.org/whl/cpu` ANTES del resto → pip lo ve satisfecho y salta los nvidia. Build: ~1h → ~1min |
| 4 | La prueba contra Ollama real (3.2) expiraba a los 60s incluso con la CPU quieta: generación a **0.17 tok/s** (5.9 s/token) en un Core Ultra 7 255H | CPU híbrido (P+E+LPE cores): el auto-detect de threads de Ollama reparte threads en cores de baja potencia y cada token (barrera de sincronización) espera al más lento | `OLLAMA_NUM_THREADS` opcional en settings + `num_thread` en la petición del `ClienteLightLM`; fijado a 6 (P-cores) en compose de desarrollo y conftest. Medido: 2m27s → 4.7s (~30x). En el ECS (vCPUs uniformes) se deja sin definir |
| 5 | La búsqueda semántica fallaba con `operator does not exist: vector <=> double precision[]` | psycopg adapta listas Python a arrays de Postgres; el operador `<=>` de pgvector exige tipo `vector` (el INSERT funcionaba por cast de asignación, la expresión no) | `AlmacenVectorial.buscar()`: embedding serializado con `json.dumps` (formato texto de pgvector) + cast explícito `::vector`. Cazado por el test de integración 2.6 |
| 6 | `docker` fallaba en shells nuevos con `docker-credential-desktop: executable file not found in %PATH%` | El CLI fuera de la app de Docker Desktop no tiene el bin dir en PATH | Prependear `C:\Program Files\Docker\Docker\resources\bin` al PATH de la sesión (§3.1) |
| 7 | El test de indexación fallaba por filas ajenas ("FAQ matrícula" del test de retrieval) | Tests de integración sin aislamiento: el fixture de retrieval trunca al inicio pero no al final | TRUNCATE defensivo al inicio del test de indexación, igual que el fixture |
| 8 | Ollama caía con `illegal instruction` en `libggml-cpu-cascadelake.so` (500 en `/api/generate`) | El flavor original enmascaraba AVX al guest pese a que la CPU física (Xeon Gold 6278C) lo tiene; Ollama elige la lib AVX512 por el NOMBRE de la CPU, no por flags | Migración a flavor `c7n.xlarge.2` (Xeon 6348, AVX2/AVX-512 expuestos). Parche previo (ocultar libs AVX → SSE42) descartado: funcional pero ~84 s por generación trivial. De paso se fijó `OLLAMA_NUM_THREADS=4` en el compose prod (determinístico en 4 vCPU — corrige §7.4: ya no se deja sin definir en el ECS) |
| 9 | `No module named app.ingest` en el contenedor de ingesta | El entrypoint documentado (`python -m app.ingest`) no existía: el paquete real es `app/ingestion` | Alias `backend/app/ingest.py` que delega en `app.ingestion.__main__.main` — el comando documentado, el `command` de los compose y el cron funcionan tal cual |
| 10 | `FileNotFoundError: data/secciones_portal.yml` al correr la ingesta | El Dockerfile no copiaba `backend/data/` (FAQs + YAML de secciones) a la imagen | `COPY backend/data ./data` en `docker/Dockerfile.backend` |
| 11 | Build fallaba: `uvloop>=0.15.1` sin pin con `--require-hashes` | El lock se generó con Python 3.14 (donde uvloop no existe); en el contenedor 3.12 el extra `[standard]` de uvicorn lo exige | Lock regenerado con Python 3.12 (pip-compile en contenedor efímero) y devuelto al repo |
| 12 | `ollama pull qwen2.5:…@sha256:…` → `400 invalid model name` | El `pull` de Ollama no soporta digests (a diferencia de `docker pull`) | Pull por tag + verificación del digest después con `ollama list` (ID debe empezar por el digest pinneado); guía §5 actualizada |
| 13 | Tras recrear el contenedor `app`, la primera consulta tardaba minutos | La caché de Hugging Face (modelo e5, ~470 MB) vivía dentro del contenedor y se perdía en cada recreate | Volumen `hf-cache` montado en `app` e `ingest` (`docker-compose.prod.yml`); también evita la re-descarga semanal del cron de ingesta |

## 8. Lecciones

- **`*.pem` en `.gitignore` pilla también certificados PÚBLICOS**: usar extensión `.crt`/`.cer` para material público de CA y reservar `.pem` para claves.
- **"Connection refused" vs timeout** (ya documentado en bitacora §4.6) y ahora **cadena TLS incompleta**: los portales UNMSM tienen rarezas de infraestructura; el scraper debe registrar fallos por página sin detenerse — el spec ya lo exigía y sirvió de red de seguridad real.
- Los subagentes en paralelo funcionan bien con alcances disjuntos (ingesta vs frontend vs pipeline central) y `tasks.md` como tablero compartido de checkboxes; el único roce fue ruff señalando archivos ajenos a mitad de ejecución, que cada dueño corrigió en su alcance.
- **En Linux, torch por defecto es CUDA**: toda imagen Docker CPU-only debe instalar torch del índice CPU de PyTorch antes que cualquier cosa que lo dependa (§7.3).
- **CPUs híbridos rompen el auto-detect de threads de Ollama**: si la generación es decenas de veces más lenta que el prompt eval, limitar `num_thread` a los P-cores (§7.4).
- **Los tests de integración contra infraestructura real cazan bugs que los mocks no ven**: 2 de los 4 bugs de D2 (cast pgvector, threads) solo aparecieron contra pgvector y Ollama reales. El costo de levantar los contenedores de prueba (§3.2) se paga solo.
- **Las claves de documentación no sirven para probar gitleaks**: `AKIAIOSFODNN7EXAMPLE` y cadenas con "test"/"fake" están en los stopwords por defecto; la prueba de detección usa un secreto sintético realista.
- **En inferencia CPU, verificar los flags del guest antes de aceptar un flavor** (`lscpu`): el nombre de la CPU puede llevar a Ollama a elegir libs AVX que el hipervisor no ejecuta (§7.8). Y un build "verificado" en local no garantiza que los comandos documentados corran en el entorno real: el despliegue D4 cazó 3 bugs que los tests no veían (§7.9–7.11).
- **Toda caché que pese (>100 MB) va en volumen**, no en el filesystem del contenedor: cada recreate la re-descarga (§7.13).

## 9. Cronología de sesiones de desarrollo

| Fecha | Sesión | Hitos |
|---|---|---|
| 2026-10-30 | **D1 — Implementación grupos 1–6** | Conciliación 39/40→41 tareas · scaffolding backend+frontend+docker+gitleaks · settings tipado · ingesta completa con scraper real (hallazgo TLS del portal FISI, §7) · guardián regex+light LM · pipeline RAG con orquestador único · API web + SPA React con arte Lima · bot de Telegram completo · 27/41 tareas verificadas (106 tests backend + 9 frontend en verde) · pendientes: verificaciones con Docker/pgvector/Ollama, DevTools 5.3, primer commit (gitleaks) y grupo 7 |
| 2026-10-31 | **D2 — Verificación de entorno, cierre de grupos 1–6** | Entorno completo instalado (Docker Desktop, gitleaks, sentence-transformers vía winget/pip, §3) · 7 tareas verificadas: 1.3 build, 1.5 Ollama+modelo, 1.6 gitleaks, 2.6 pgvector, 3.2 Ollama real (8.8s), 4.1 retrieval, 5.3 visual Playwright 390px · 4 bugs cazados y corregidos (§7.3–7.6): torch CUDA en Docker, threads CPU híbrido, cast pgvector, aislamiento de tests · hook gitleaks conciliado a `.githooks/` único · guía de despliegue creada (`docs/guia-deploy.md`: ECS, Vercel, webhook, cron, rollback) · 34/41 tareas, 110/110 tests backend + 9 frontend en verde |
| 2026-10-31 | **D3 — Hardening de seguridad LLM (cambio `harden-llm-security`)** | Análisis OWASP Top 10 LLM 2025 (`docs/owasp10llms-analisis.md`) + cambio OpenSpec propuesto y aplicado · 5 subagentes en paralelo sobre base compartida (settings, `ERROR_SERVICIO`, `guard/fuga.py`) · 19/20 tareas: aislamiento de contexto anti-inyección indirecta, guardián fail-closed, canario anti-fuga, citas fieles, LLM acotado (max_tokens/timeout), límite web por IP + memoria de contadores acotada, webhook sin token en URL + anti-replay, redacción de logs, anti-SSRF en ingesta, URLs seguras en la web, lockfile con hashes + digests de imágenes/modelos · 146 tests backend + 11 frontend en verde, lock verificado con instalación limpia, pip-audit sin CVEs · venv reconstruido (esta máquina no traía el de D2) · pendientes: 6.3 (docker compose config) y grupo 7 |
| 2026-10-31 | **D4 — Despliegue en ECS (grupo 7) + optimización de latencia** | Stack prod Up con TLS · modelo light LM verificado por digest · **ingesta: 242 fragmentos** · webhook Telegram registrado + cron semanal · acceso SSH por clave operado desde la sesión · 6 incidentes cazados y resueltos (§7.8–7.13): AVX enmascarado (migración a `c7n.xlarge.2`), alias `app.ingest`, `COPY backend/data`, lock regenerado con 3.12, pull por tag + digest, volumen `hf-cache` · cambio `reduce-validation-latency`: validación acotada (3×600) → **latencia 32–40 s → ~11 s** · `harden-llm-security` 20/20 · 39/41 tareas de `add-fisi`; pendientes 7.5 (E2E Telegram + rotar token) y 7.6 (Vercel) · 150 tests unitarios en verde |

## 10. Convención para actualizar esta bitácora

1. **Al cerrar cada sesión**: agregar fila a §9 y reescribir "Estado actual".
2. **Por grupo de tareas** (§4): marcar cada tarea con `[x]` solo cuando su verificación de `tasks.md` pasó; si la verificación no pudo ejecutarse en este entorno, dejar `[ ]` con nota *verificación pendiente* y cómo ejecutarla.
3. **Decisiones de implementación** nuevas: fila en §2, numeración consecutiva.
4. **Incidentes/desvíos** (§7): causa y solución; **lecciones** (§8) si aplica a futuro.
5. No borrar historia; las correcciones se añaden junto al original.

## Pendientes

- [x] Verificar 1.3 y 1.5 con Docker (D2, §3).
- [x] Tests de integración pgvector (2.6, 4.1) con `TEST_DATABASE_URL` + extra `[ingest]` (D2, §3.3).
- [x] Prueba de integración contra Ollama real (3.2) (D2, tras el fix de threads §7.4).
- [x] Revisión en viewport móvil de la identidad visual (5.3) (D2, Playwright §3.4).
- [ ] Commit/push de la implementación + fixes de despliegue (equipo) — **antes**: `git config core.hooksPath .githooks` (una vez por clon). Incluye: `backend/app/ingest.py`, `COPY backend/data` en el Dockerfile, compose prod (`hf-cache`, `OLLAMA_NUM_THREADS`), lock regenerado con 3.12, guía §5/§12 y el cambio `reduce-validation-latency`.
- [x] Grupo 7 desplegado en el ECS (D4, ver §4) — salvo 7.5 y 7.6.
- [x] Cambio `harden-llm-security` aplicado y completo (20/20; la 6.3 se verificó en el ECS, D4).
- [x] Cambio `reduce-validation-latency` aplicado y verificado (D4): latencia ~11 s en caliente.
- [ ] 7.5: probar Telegram end-to-end (mensaje real) y **rotar el token del bot** (viajó en URLs antes de la ruta fija del webhook).
- [ ] 7.6: desplegar el frontend en Vercel (equipo) y ajustar `CORS_ORIGINS` con la URL real.
- [ ] Seguridad del ECS: rotar el password de root (quedó en el historial de la sesión) y volver a `PasswordAuthentication no`.
- [x] `/opsx:archive` de `harden-llm-security` y `reduce-validation-latency` (D4): sus requirements ya viven en `openspec/specs/` (7 capabilities; los *Purpose* se ajustaron a mano porque el CLI conserva el existente al fusionar).
- [ ] `/opsx:archive` de `add-fisi-rag-chatbot` tras cerrar 7.5/7.6 — archivará **último** para fusionar sus requirements base sobre los ya existentes.
