# Backend de InnovaBot

Backend del chatbot RAG de la FISI (UNMSM): API FastAPI, pipeline de respuesta
e ingesta de conocimiento hacia PostgreSQL con pgvector. Para el diseño y los
specs completos, ver `openspec/changes/add-fisi-rag-chatbot/` en la raíz del repo.

## Requisitos

- Python 3.12+
- Un venv con las dependencias: `pip install -e ".[dev]"` (y `".[ingest]"` si vas
  a ejecutar la ingesta con embeddings reales, ver abajo)
- Un archivo `.env` con las variables de entorno (copia `backend/.env.example`)

## Ingesta de conocimiento

La ingesta recopila las 4 fuentes (noticias del portal FISI, PDFs del portal,
FAQs curadas y secciones del portal central UNMSM), genera los embeddings con
sentence-transformers y los indexa en PostgreSQL (pgvector) con deduplicación
por hash de contenido.

### Ejecución

Desde la carpeta `backend/` (las rutas de `data/` son relativas a ella):

```bash
.venv/Scripts/python -m app.ingest        # Windows
python -m app.ingest                      # Linux (ECS, bajo cron semanal)
```

Requisitos de esa ejecución:

- Variables de entorno del archivo `.env` cargadas (ver abajo); en particular
  `DATABASE_URL` apuntando a la base `rag_fisi` del RDS con pgvector.
- El extra `ingest` instalado en el entorno que ejecuta la ingesta, porque los
  embeddings usan sentence-transformers (descarga ~470 MB de modelo la primera vez):

  ```bash
  pip install ".[ingest]"
  ```

Comportamiento:

- Crea la tabla `fragmentos` (con índice HNSW) si no existe — es idempotente.
- Es re-ejecutable: contenido idéntico produce el mismo hash (SHA-256 del
  contenido normalizado) y no inserta duplicados; un documento actualizado
  deja obsoleta (`obsoleto=TRUE`) su versión anterior por URL.
- Los fallos por página/PDF/sección se registran en el log y no detienen la
  ejecución; si la ejecución completa ingiere 0 fragmentos, termina con código 1
  como alerta.
- El scraper se identifica con su propio User Agent y limita los PDFs por
  ejecución (5) para ser educado con los portales.
- Nota TLS: el portal FISI sirve una cadena de certificados incompleta; el
  paquete incluye el certificado intermedio público correcto
  (`app/ingestion/intermedio_sectigo.crt`, descargado del AIA del certificado)
  para que la verificación TLS funcione también en Linux. No es un secret.
- Política anti-SSRF (cambio `harden-llm-security`, LLM04): los PDFs solo se
  descargan desde los dominios oficiales (`sistemas.unmsm.edu.pe`,
  `unmsm.edu.pe`) y los hosts extra de `INGESTA_HOSTS_PERMITIDOS`; toda URL
  cuyo host resuelva a una IP privada/loopback/link-local se descarta y queda
  registrada. Además, el contenido descargado debe ser un PDF real (cabecera
  `%PDF-`) para procesarse.

### Variables de entorno

La plantilla completa está en `backend/.env.example` (copiar a `backend/.env`,
que está en `.gitignore` — el repo es público). Las relacionadas con la ingesta:

| Variable | Obligatoria | Descripción |
| --- | --- | --- |
| `DATABASE_URL` | Sí | PostgreSQL con pgvector (RDS `rag_fisi` en producción) |
| `EMBEDDINGS_MODEL` | No | Modelo de embeddings (default `intfloat/multilingual-e5-small`) |
| `EMBEDDINGS_REVISION` | No | Revisión fija del modelo en Hugging Face (integridad, `harden-llm-security` LLM03) |
| `INGESTA_HOSTS_PERMITIDOS` | No | Hosts extra de la allowlist anti-SSRF, separados por coma |
| `FAQS_MD` | No | Ruta del archivo de FAQs curadas (default `data/faqs.md`) |
| `SECCIONES_PORTAL_YML` | No | Ruta del YAML de secciones del portal central (default `data/secciones_portal.yml`) |

### Formato del YAML de secciones del portal central

`data/secciones_portal.yml` delimita qué secciones de `unmsm.edu.pe` se
scrapean — solo las listadas se ingieren:

```yaml
secciones:
  - nombre: Admisión
    url: https://www.unmsm.edu.pe/formacion-academica/admision
  - nombre: Vida universitaria (bienestar)
    url: https://www.unmsm.edu.pe/comunidad/vida-universitaria
```

Cada página se ingiere como fragmento `tipo=portal` con la fecha de consulta
como fecha. Para añadir o quitar una sección, edita la lista y vuelve a
ejecutar la ingesta.

### Formato del Markdown de FAQs curadas

`data/faqs.md` mantiene las preguntas frecuentes que el equipo cura a mano.
Cada encabezado de nivel 2 (`## ¿Pregunta?`) con su respuesta genera un
fragmento único con `tipo=faq` (máxima prioridad en el retrieval):

```markdown
# Título del archivo (no genera fragmento)

## ¿Pregunta?

Respuesta en Markdown. Llega hasta el siguiente encabezado `## `.
```

- Un Q&A sin respuesta se descarta.
- Re-ejecutar la ingesta no duplica entradas (mismo contenido → mismo hash);
  editar una respuesta la reemplaza en el siguiente ciclo de ingesta.

## Pipeline de respuesta (contrato)

Ambas interfaces (web y Telegram) pasan por el **mismo orquestador**
(`app/rag/orquestador.py`), que aplica los chequeos del más barato al más
caro: longitud → rate limit → regex → light LM (guard + clasificación +
reescritura en UNA llamada) → retrieval pgvector (boost a FAQs) → LLM
principal → validación anti-alucinación (1 reintento con feedback) → filtro
de salida anti-fuga → respuesta con citas de los fragmentos usados.

### Entrada

`procesar(consulta, identidad, interfaz)`:

- `consulta`: el texto del usuario (máx. 500 caracteres; no se trunca).
- `identidad`: `telegram:<user_id>` o `web:<session_id>` — contra ella corren
  los límites (5/minuto, 30/hora, ventana deslizante en memoria).
- `interfaz`: `"telegram"` o `"web"` (solo para el log estructurado).

### Salida

`{reply, citas: [{titulo, url}], estado}` con exactamente cuatro estados:

| Estado | Significado |
| --- | --- |
| `ok` | Respuesta generada y validada, con las citas de los fragmentos usados (dedup por URL) |
| `bloqueada` | Rechazada por longitud (>500 chars), por el guardián (regex o light LM), por estar fuera de alcance o por detectarse una fuga de instrucciones internas en la salida; `reply` es el mensaje estándar correspondiente |
| `sin_resultados` | Sin fragmentos con relevancia suficiente, la validación anti-alucinación falló dos veces, o el LLM principal falló (timeout/error); `reply` es el mensaje estándar correspondiente |
| `limitada` | Rate limit excedido (por identidad o por IP en la web); `reply` indica cuánto esperar |

Mapeos documentados (los specs definen solo estos 4 estados): una consulta
fuera de alcance responde `bloqueada` con el mensaje de temas atendidos; un
fallo doble de validación responde `sin_resultados` con el mensaje de
información no disponible; un fallo del LLM principal (timeout o error del
servicio) responde `sin_resultados` con un mensaje amigable sin detalles
técnicos.

Endurecimiento del cambio `harden-llm-security`:

- **Citas fieles**: el LLM principal cierra su respuesta con un marcador
  `{"fuentes": [n]}`; el orquestador lo extrae y cita solo esos fragmentos
  (el `reply` entregado no incluye el marcador). Sin marcador válido, cita
  todas las fuentes recuperadas — nunca se pierden citas.
- **Aislamiento de contexto**: los fragmentos viajan delimitados
  (`<<<FRAGMENTO n>>> … <<<FIN>>>`) y los system prompts ordenan tratarlos
  como datos, nunca como instrucciones (anti prompt-injection indirecta).
- **Filtro anti-fuga**: un canario por proceso viaja en los system prompts;
  si la respuesta generada lo contiene (fuga verbatim de instrucciones), se
  responde `bloqueada` con el mensaje estándar.
- **Consumo acotado**: cada llamada al LLM principal lleva `LLM_MAX_TOKENS`
  y `LLM_TIMEOUT_SECONDS`; la web aplica además un límite por IP
  (`RATE_LIMIT_IP_PER_MINUTE`) además del límite por identidad.

### Ejemplo ejecutable

Desde `backend/`, el ejemplo corre el pipeline completo con clientes falsos
(sin red) e imprime la salida en el contrato exacto:

```bash
.venv/Scripts/python ejemplo_contrato.py
```

## API web

`POST /api/chat` (spec web-ui): body `{"query": string}` más el header
`X-Session-ID` (UUID que genera el frontend en la primera carga). Responde el
contrato de arriba; **HTTP 429** cuando el estado es `limitada` (también si
falta el header). CORS únicamente para el origen de Vercel (`CORS_ORIGINS`).

Arrancar en desarrollo:

```bash
.venv/Scripts/python -m uvicorn app.main:app --reload
```

## Webhook de Telegram

`POST /telegram/webhook` (spec telegram-ui + cambio `harden-llm-security`,
LLM02): ruta fija — el token del bot **no** viaja en la URL ni llega a los
access logs. La autenticación es el header `X-Telegram-Bot-Api-Secret-Token`
que Telegram firma en cada petición (401 si no coincide). Los updates
repetidos (mismo `update_id` dentro de una ventana de 1 h) se descartan sin
reprocesar (anti-replay). Solo se atienden chats privados; `/start` y
`/help` se responden sin entrar al pipeline; el resto de mensajes usa el
mismo orquestador con identidad `telegram:<user_id>`.

Registro del webhook en producción (requiere el dominio con TLS del grupo 7;
los valores vienen de las variables de entorno, nunca del repo):

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook" \
     -d "url=https://<dominio>/telegram/webhook" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>" \
     -d 'allowed_updates=["message"]'
```

## Cadena de suministro (cambio `harden-llm-security`, LLM03)

- **Dependencias base fijadas**: `requirements.lock` (generado con
  `pip-compile --generate-hashes`) instala versiones exactas verificadas por
  hash. Regenerar tras cambiar `pyproject.toml`:

  ```bash
  pip install pip-tools
  pip-compile --generate-hashes --output-file requirements.lock pyproject.toml
  ```

  El extra `[ingest]` (sentence-transformers/torch) queda fuera del lock:
  torch es plataforma-específica y el Dockerfile lo instala CPU-first desde
  el índice de PyTorch antes que el resto.
- **Auditoría de vulnerabilidades** (manual mientras no haya CI):

  ```bash
  pip install pip-audit
  pip-audit --require-hashes -r requirements.lock
  ```

- **SBOM** (cuando exista CI; mientras tanto, paso manual): `syft dir:. -o
  cyclonedx-json > sbom.json` sobre el build de la imagen.
- **Modelos e imágenes fijados**: `EMBEDDINGS_REVISION` (commit de Hugging
  Face del modelo de embeddings), digest del modelo de Ollama y digests de
  las imágenes de contenedor — ver `docs/guia-deploy.md`.

## Despliegue y operación (tarea 7.7)

El paso a paso completo vive en `docs/guia-deploy.md` (ECS + Vercel, con
verificación y problemas comunes). Lo esencial para operar el ECS:

```bash
# Despliegue de cambios (manual, por SSH — repo público, pull sin credenciales)
cd /opt/innovabot
git pull
docker compose -f docker/docker-compose.prod.yml build
docker compose -f docker/docker-compose.prod.yml up -d
curl -fsS https://innovabot.duckdns.org/docs -o /dev/null && echo "OK"

# Disparo manual de la ingesta (contenido urgente; el cron semanal corre lunes 04:00)
docker compose -f docker/docker-compose.prod.yml --profile ingest run --rm -T ingest
```

## Tests

Desde `backend/`:

```bash
.venv/Scripts/python -m pytest     # todo (los de integración se saltan solos)
.venv/Scripts/python -m pytest tests/unit -q      # solo unitarios
.venv/Scripts/python -m ruff check .
```

Los tests unitarios mockean los clientes externos (embeddings incluidos): no
descargan modelos ni tocan la red.

### Tests de integración (pgvector real)

Los tests de `tests/integration/` usan embeddings y base de datos reales, así
que se saltan limpiamente si no hay `TEST_DATABASE_URL`. Con un pgvector local
(vía Docker):

```bash
docker run -d --name pgvector-test \
    -e POSTGRES_PASSWORD=test -p 5432:5432 pgvector/pgvector:pg18

# PowerShell, desde backend/:
$env:TEST_DATABASE_URL = "postgresql://postgres:test@localhost:5432/postgres"
.venv/Scripts/python -m pytest tests/integration -q
```

Requiere también el extra `ingest` (sentence-transformers) en el entorno.
