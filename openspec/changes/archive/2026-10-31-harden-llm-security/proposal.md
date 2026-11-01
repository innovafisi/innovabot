# Proposal — Hardening de seguridad LLM (OWASP Top 10 2025)

## Why

La revisión de seguridad de InnovaBot contra el OWASP Top 10 para Aplicaciones
LLM (2025) — registrada en `docs/owasp10llms-analisis.md` — identificó riesgos
**Altos** en dos frentes (prompt injection indirecta y consumo no acotado) y
**Medio-Altos** en otros dos (fuga de información, envenenamiento/SSRF). El
MVP ya tiene defensas (guard de dos capas, validación anti-alucinación, rate
limit), pero quedan huecos que, en un bot público de la UNMSM, pueden derivar
en respuestas manipuladas, filtración del token del bot, coste ilimitado del
LLM o exfiltración interna vía la ingesta. Esta propuesta cierra esos huecos
sin reabrir las decisiones de producto ya tomadas en `add-fisi-rag-chatbot`.

## What Changes

- **Prompt injection indirecta (LLM01):** aislar el contenido recuperado como
  *datos* en los prompts de generación y validación, con instrucción explícita
  de ignorar instrucciones embebidas; endurecer el guard (fail-closed ante
  ambigüedad y validación de su veredicto).
- **Fuga de información (LLM02/LLM07):** sacar el token del bot de la ruta del
  webhook (autenticidad solo por el header secreto), silenciar el access log de
  esa ruta, redactar errores (sin cuerpos de respuesta ni DSN) y añadir filtro
  de salida contra fuga de system prompt.
- **Consumo no acotado (LLM10):** límite adicional por IP, acotación de memoria
  de contadores (TTL/tope) y `max_tokens`+`timeout` explícitos en el LLM
  principal.
- **Envenenamiento / SSRF (LLM04):** allowlist de hosts y bloqueo de IP
  privadas/link-local en la descarga de PDFs; verificación de PDF real.
- **Fidelidad de citas (LLM09):** citar solo los fragmentos realmente usados.
- **Manejo de salida (LLM05):** validar esquema `http`/`https` de las URLs de
  citas antes de renderizarlas.
- **Cadena de suministro (LLM03):** lockfile con hashes, `revision`/hash del
  modelo de embeddings, digests de imágenes/Ollama y SBOM/escaneo en CI.
- **Telegram:** ignorar updates repetidos (replay) por `update_id`.

## Capabilities

### New Capabilities

- `supply-chain-integrity`: fijar y verificar la procedencia del software y los
  modelos (dependencias, imágenes de contenedor, modelos de embeddings/Ollama)
  y detectar vulnerabilidades conocidas.

### Modified Capabilities

- `prompt-injection-guard`: aislamiento de contenido recuperado (inyección
  indirecta), guard fail-closed y protección de salida contra fuga de prompt.
- `rag-answering`: citas fieles a los fragmentos usados y llamadas acotadas al
  LLM principal (`max_tokens`, `timeout`).
- `usage-limits`: límite por IP, acotación de memoria de contadores y control
  del costo de generación.
- `telegram-ui`: autenticación del webhook sin exponer el token en la URL y
  rechazo de updates repetidos.
- `knowledge-ingestion`: restricción de descargas a hosts permitidos (anti-SSRF)
  y verificación del tipo de contenido.
- `web-ui`: saneamiento de las URLs de citas.

## Impact

- **Código backend**: `app/guard/` (aislamiento, guard), `app/rag/`
  (generación, validación, citas, orquestador), `app/core/` (límites, clientes,
  settings, logs), `app/interfaces/` (api, telegram), `app/ingestion/pdfs.py`.
- **Frontend**: `frontend/src/components/ChatView.tsx` (esquema de URLs).
- **Configuración**: nuevas variables (`RATE_LIMIT_IP_PER_MINUTE`,
  `LLM_MAX_TOKENS`, `LLM_TIMEOUT_SECONDS`, `TELEGRAM_WEBHOOK_PATH`,
  allowlist de ingesta, `embeddings_revision`).
- **Despliegue**: `docker/docker-compose.prod.yml` (digests de imágenes),
  webhook registrado contra la nueva ruta sin token; rotación del token del bot.
- **Sin cambios de UX** para el usuario final: textos y flujo de respuesta se
  mantienen; los estados del contrato no cambian.
- **Depende de** `add-fisi-rag-chatbot` (extiende sus capabilities). No rompe
  sus specs: solo añade requisitos.
