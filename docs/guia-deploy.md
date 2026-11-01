# Guía de despliegue — InnovaBot

Paso a paso del despliegue en Huawei Cloud ECS + Vercel (grupo 7 de `tasks.md`).
Complementa a `backend/README.md` (operación del backend) y a `docs/bitacora.md`
(infraestructura ya provisionada). Todas las tareas de verificación citadas
(7.1–7.7) corresponden a `openspec/changes/add-fisi-rag-chatbot/tasks.md`.

---

## 0. Estado previo (ya completado — verificar antes de empezar)

| Requisito | Estado | Verificación rápida |
|---|---|---|
| ECS `ecs-innovabot` (4 vCPU / 8 GB, Ubuntu, EIP) | ✅ configurado | `ssh deploy@<EIP>` entra sin password |
| Docker + compose plugin en el ECS | ✅ instalado | `docker version` (server responde) |
| Swap 4 GB + timezone America/Lima | ✅ | `free -h`; `timedatectl` |
| RDS `rds-innovabot` (PostgreSQL 18 + pgvector, DB `rag_fisi`) | ✅ | `nc -zv 192.168.0.168 5432` → succeeded |
| SG `sg-innova`: 80/443 abiertos, SSH restringido, 5432 solo VPC | ✅ | consola Huawei |
| DNS `innovabot.duckdns.org` → EIP | ✅ | `nslookup innovabot.duckdns.org` |
| Credenciales (API key MaaS, token BotFather, secret webhook) | ✅ | en `backend/.env` local; se copian al ECS en el paso 3 |

> Si `nc` da *timeout*: el security group está bloqueando (paquete descartado).
> Si da *connection refused*: IP equivocada o instancia caída — verificar la IP
> privada en la consola del RDS. (Lección S1, bitacora §4.6.)

---

## 1. Archivos de producción (tarea 7.1)

El compose de desarrollo (`docker/docker-compose.yml`) publica Ollama en
`127.0.0.1:11434` para poder verificarlo desde el host. En producción **solo
Caddy publica puertos (80/443)**; `app` y `ollama` viven en la red interna de
Docker.

Ambos archivos ya **viven versionados en `docker/`** (`docker-compose.prod.yml`
y `Caddyfile`): se clonan con el repo y no se crean a mano en el ECS (así el
`git pull` de §10 los actualiza y el rollback funciona). Se muestran aquí como
referencia:

**`docker/docker-compose.prod.yml`** — stack completo de producción:

```yaml
# Stack de PRODUCCIÓN en el ECS (tarea 7.1 de tasks.md).
# Diferencias con el de desarrollo: Caddy publica 80/443 con Let's Encrypt,
# Ollama NO publica puertos (interno), restart: always.
# Uso: docker compose -f docker/docker-compose.prod.yml up -d
#      docker compose -f docker/docker-compose.prod.yml --profile ingest run --rm ingest

services:
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    env_file: ../backend/.env
    environment:
      OLLAMA_BASE_URL: http://ollama:11434
      # OLLAMA_NUM_THREADS: NO definir aquí — el ECS tiene vCPUs uniformes y el
      # auto-detect de Ollama es correcto (bitacora-dev §7.4: solo los CPUs
      # híbridos de desarrollo necesitan el límite).
    restart: always
    depends_on:
      - ollama

  ingest:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    env_file: ../backend/.env
    environment:
      OLLAMA_BASE_URL: http://ollama:11434
    command: python -m app.ingest
    profiles:
      - ingest
    restart: "no"
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama:latest
    environment:
      # Una generación a la vez: evita disputa de RAM (design.md §Modelos).
      OLLAMA_NUM_PARALLEL: "1"
    volumes:
      - ollama-data:/root/.ollama
    restart: always
    # SIN "ports": interno. Solo Caddy expone 80/443 en la EIP.

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data       # certs Let's Encrypt persisten entre reinicios
      - caddy-config:/config
    restart: always
    depends_on:
      - app

volumes:
  ollama-data:
  caddy-data:
  caddy-config:
```

**`docker/Caddyfile`** — TLS automático (tarea 7.2):

```caddyfile
# TLS automático con Let's Encrypt contra el DNS gratuito (design.md §Despliegue).
# Si algún día hay subdominio institucional, se cambia esta línea y nada más.
innovabot.duckdns.org {
    reverse_proxy app:8000
}
```

Caddy gestiona la emisión y renovación del certificado solo: al arrancar,
valida el dominio (puerto 80) y emite para `innovabot.duckdns.org`.

---

## 2. Código en el ECS

El repo es público: clone por HTTPS sin credenciales (pull-only, sin capacidad
de push desde el servidor).

```bash
sudo mkdir -p /opt/innovabot && sudo chown deploy:deploy /opt/innovabot
git clone https://github.com/innovafisi/innovabot.git /opt/innovabot
cd /opt/innovabot

# Hook de gitleaks también en el servidor (una vez por clon):
git config core.hooksPath .githooks
```

---

## 3. Variables de entorno en el ECS

```bash
cd /opt/innovabot/backend
cp .env.example .env
nano .env   # o el editor que prefieras
```

Valores de producción:

```ini
MAAS_API_KEY=<API key de Huawei MaaS>
MAAS_BASE_URL=<endpoint de MaaS>
MAIN_LLM_MODEL=deepseek-v4.1-flash

OLLAMA_BASE_URL=http://ollama:11434      # nombre del servicio en el compose
LIGHT_LLM_MODEL=qwen2.5:3b-instruct-q4_K_M
# OLLAMA_NUM_THREADS: NO definir (vCPUs uniformes)

DATABASE_URL=postgresql://root:<contraseña RDS>@192.168.0.168:5432/rag_fisi

TELEGRAM_BOT_TOKEN=<token de BotFather>
TELEGRAM_WEBHOOK_SECRET=<secret elegido por el equipo>

CORS_ORIGINS=https://innovabot.vercel.app

# ---- Hardening LLM (cambio harden-llm-security; defaults razonables) ----
RATE_LIMIT_IP_PER_MINUTE=20     # límite web por IP (además del por usuario)
LLM_MAX_TOKENS=512              # tope de tokens por respuesta del LLM principal
LLM_TIMEOUT_SECONDS=30          # timeout de la llamada al LLM principal
EMBEDDINGS_REVISION=614241f622f53c4eeff9890bdc4f31cfecc418b3  # revisión HF del modelo e5
INGESTA_HOSTS_PERMITIDOS=       # hosts extra de la allowlist anti-SSRF (vacío = solo portales UNMSM)
```

> `backend/.env` está en `.gitignore` y gitleaks lo vigila: jamás commitearlo.

---

## 4. Arrancar el stack (tarea 7.1)

```bash
cd /opt/innovabot
docker compose -f docker/docker-compose.prod.yml build
docker compose -f docker/docker-compose.prod.yml up -d
docker compose -f docker/docker-compose.prod.yml ps   # app, ollama, caddy Up
```

**Smoke check a través de Caddy** (tarea 7.1: el endpoint responde vía TLS):

```bash
curl -fsS https://innovabot.duckdns.org/docs -o /dev/null && echo "OK: API viva detrás de Caddy"
```

- La primera vez, Caddy tarda unos segundos en emitir el certificado.
- Si el certificado no emite: verificar que el DNS resuelve a la EIP y que el
  SG permite 80 **y** 443 (Let's Encrypt usa 80 para la validación).

---

## 5. Light LM en el volumen de Ollama (tarea 7.3)

> **Integridad del modelo (harden-llm-security, LLM03):** `ollama pull` NO
> acepta `@sha256:` (responde `400 invalid model name`); se descarga por tag y
> se **verifica el digest después** contra el valor pinneado (config digest,
> obtenido del registry de Ollama, 2026-10-31):
> `sha256:161ddde4c9cd07c9f1ccb4e0167c434bce72caeb3fc1844262fa66bc877b0426`.

```bash
cd /opt/innovabot
docker compose -f docker/docker-compose.prod.yml exec ollama \
    ollama pull qwen2.5:3b-instruct-q4_K_M
```

Verificación de que el modelo quedó en el volumen y con el digest esperado
(tarea 7.3) — en producción Ollama no publica puertos y la imagen no trae
`curl`, así que se usa `ollama list` desde dentro del contenedor:

```bash
docker compose -f docker/docker-compose.prod.yml exec ollama ollama list
# NAME                          ID           SIZE
# qwen2.5:3b-instruct-q4_K_M    161ddde4c9cd 1.9 GB   ← debe empezar por el digest pinneado
```

Y una consulta real de guardián (debe devolver JSON parseable; en el ECS de
4 vCPU dedicados el objetivo de latencia es < 10 s por respuesta completa).
Con `exec -T` y heredoc se evitan los problemas de comillas/saltos del `-c`
multilínea:

```bash
docker compose -f docker/docker-compose.prod.yml exec -T app python - <<'PY'
from app.core.clientes import ClienteLightLM
from app.guard.light_lm_guard import evaluar_consulta
r = evaluar_consulta('¿hasta cuándo puedo matricularme en la FISI?', ClienteLightLM())
print(r.safe, r.categoria, r.consulta_reescrita)
PY
```

---

## 6. Base de datos: tablas + primera ingesta (tarea 7.4)

La ingesta crea la tabla y el índice HNSW de forma idempotente
(`AlmacenVectorial.crear_tabla`), así que la primera ejecución deja el RDS listo:

```bash
cd /opt/innovabot
docker compose -f docker/docker-compose.prod.yml --profile ingest run --rm ingest
```

Verificar que el índice contiene fragmentos de las **4 fuentes** (noticias,
PDFs, FAQs, portal central):

```bash
docker compose -f docker/docker-compose.prod.yml exec app python -c "
import os, psycopg
conn = psycopg.connect(os.environ['DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute('SELECT tipo, count(*) FROM fragmentos WHERE obsoleto = FALSE GROUP BY tipo')
    print(cur.fetchall())"
```

> La primera ingesta descarga `multilingual-e5-small` (~470 MB) dentro del
> contenedor y scrapea los portales: puede tardar. Los fallos de página se
> registran sin detener la ingesta (spec knowledge-ingestion).

---

## 7. Webhook de Telegram (tarea 7.5)

> **Cambio `harden-llm-security` (LLM02):** la ruta es FIJA
> (`/telegram/webhook`) y el token del bot **ya no viaja en la URL** — la
> autenticación es el header `X-Telegram-Bot-Api-Secret-Token` que firma
> Telegram. Al desplegar esta versión por primera vez: re-registrar el
> webhook con la URL nueva y **rotar el token** en BotFather (el token
> antiguo viajó en URLs/access logs).

Con el stack vivo y TLS emitido:

```bash
source /opt/innovabot/backend/.env
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://innovabot.duckdns.org/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
  -d "allowed_updates=[\"message\"]"
```

Verificar el registro y probar end-to-end (tarea 7.5): enviar un mensaje real
al bot desde Telegram y recibir respuesta con citas. También:

```bash
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool
# url correcta, no pending_update_count, no last_error_message
```

---

## 8. Frontend en Vercel (tarea 7.6)

1. En **https://vercel.com** → *Add New… → Project* → importar el repo
   `innovafisi/innovabot` (cuenta con acceso al repo).
2. **Root Directory**: `frontend/` (Vercel autodetecta Vite).
3. **Environment Variable** (Production y Preview):
   `VITE_API_URL = https://innovabot.duckdns.org`
   — sin esta variable el frontend corre en modo prototipo (respuestas falsas).
4. *Deploy*. Cada push a `main` redespliega automáticamente.

Verificación (tarea 7.6): abrir la URL de Vercel en móvil y escritorio — chat
funcional contra el backend, colores FISI, sin scroll horizontal. Documentar la
URL en `backend/README.md`.

---

## 9. Cron semanal de ingesta + disparo manual

```bash
crontab -e
```

```cron
# Ingesta semanal de InnovaBot: lunes 04:00 (America/Lima, host en ese TZ).
# Log propio para poder auditar corridas sin depurar docker.
0 4 * * 1 cd /opt/innovabot && docker compose -f docker/docker-compose.prod.yml --profile ingest run --rm ingest >> /var/log/innovabot-ingesta.log 2>&1
```

**Disparo manual** para contenido urgente (ej. aviso de matrícula recién
publicado): el mismo comando del paso 6.

---

## 10. Despliegue de cambios y rollback (tarea 7.7)

Procedimiento estándar de actualización:

```bash
cd /opt/innovabot
git pull                                            # repo público, sin credenciales
docker compose -f docker/docker-compose.prod.yml build
docker compose -f docker/docker-compose.prod.yml up -d   # recrea solo lo cambiado
curl -fsS https://innovabot.duckdns.org/docs -o /dev/null && echo "OK"
```

**Rollback** (cambio problemático):

```bash
cd /opt/innovabot
git checkout <commit-o-tag-anterior>
docker compose -f docker/docker-compose.prod.yml build
docker compose -f docker/docker-compose.prod.yml up -d
```

El índice en el RDS es recreable desde cero re-ejecutando la ingesta; los
volúmenes de Ollama (modelo) y Caddy (certificados) sobreviven a despliegues.

---

## 11. Verificación end-to-end final

| # | Qué | Cómo |
|---|---|---|
| 1 | API viva con TLS | `curl -fsS https://innovabot.duckdns.org/docs` |
| 2 | Chat web funcional | URL de Vercel → consulta real → respuesta con citas |
| 3 | Bot de Telegram | mensaje real → respuesta con citas en el mismo chat |
| 4 | Límites activos | 6 consultas rápidas → mensaje de límite (web y Telegram) |
| 5 | Ingesta indexada | conteo por `tipo` (paso 6) con las 4 fuentes |
| 6 | Logs limpios | `docker compose -f docker/docker-compose.prod.yml logs --tail 50 app` |

---

## 12. Problemas comunes

| Síntoma | Causa probable | Fix |
|---|---|---|
| Certificado no emite | DNS no apunta a la EIP, o el SG bloquea 80/443 | `nslookup` + reglas del SG; Caddy reintenta solo |
| `nc` al RDS: timeout | SG bloquea 5432 desde la VPC | regla inbound 5432 desde 192.168.0.0/16 |
| `nc` al RDS: refused | IP equivocada o instancia caída | IP privada en la consola del RDS (lección bitacora §4.6) |
| Ollama da 500 y `dmesg` muestra `illegal instruction ... libggml-cpu-cascadelake.so` | El flavor enmascara AVX al guest; Ollama elige la lib AVX512 por el nombre de la CPU | Migrar a un flavor que exponga AVX (se usó `c7n.xlarge.2`); verificar con `lscpu` (flags avx) antes de aceptar el flavor (incidente D4, bitacora-dev §7.8) |
| `ollama pull modelo@sha256:...` → `400 invalid model name` | El `pull` de Ollama no soporta digests | Bajar por tag y verificar el digest después con `ollama list` (paso 5) |
| `No module named app.ingest` | Deploy sin el último código | Resuelto en D4: `backend/app/ingest.py` es alias de `app.ingestion`; hacer `git pull` y rebuild |
| Ingesta falla contra el portal FISI | Cadena TLS incompleta del portal | Ya resuelto en la imagen (`intermedio_sectigo.crt`); si cambia el certificado del portal, actualizar ese bundle |
| Ollama lento en el ECS | RAM justa (modelo + ingesta simultáneos) | El swap de 4 GB es la red de seguridad; correr la ingesta en el cron de madrugada (ya lo hace) |
| Web carga pero las respuestas son de ejemplo | Falta `VITE_API_URL` en Vercel | paso 8.3; redeployar |
| Web carga pero el chat da error de red | CORS: `CORS_ORIGINS` no coincide con la URL real de Vercel | actualizar `backend/.env` y `up -d` |
| Telegram no responde | Webhook sin registrar o con errores | `getWebhookInfo` (paso 7); verificar secret y token |
