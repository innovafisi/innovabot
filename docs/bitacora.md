# Bitácora — InnovaBot

> **Documento vivo**: memoria operativa del proyecto. Convención de actualización en la §10.
> Toda la planificación formal vive en OpenSpec (`openspec/`); esta bitácora registra el *cómo llegamos ahí*.

## Estado actual (2026-10-31, cierre de sesión 2)

- **Implementación local completa**: grupos 1–6 del cambio `add-fisi-rag-chatbot` (34/41 tareas) — backend FastAPI, ingesta, guardián, pipeline RAG, API web, SPA React y bot de Telegram, con **110/110 tests en verde** (unit + integración).
- Planificación completa, validada y revisada (4 conflictos de specs corregidos en S1, §7).
- Infraestructura Huawei Cloud **provisionada y verificada** (ECS, RDS con pgvector, red y security groups); ECS listo para desplegar.
- DNS `innovabot.duckdns.org` apuntando a la EIP; entorno local con Docker, Ollama + `qwen2.5:3b` y pgvector de prueba operativos.
- gitleaks activo (pre-commit + config versionada); `backend/.env` con credenciales reales verificado **fuera** del repo (gitignored, no trackeado).
- **Hardening de seguridad LLM aplicado (D3)**: cambio `harden-llm-security` (19/20 tareas) — análisis y mitigaciones OWASP Top 10 LLM 2025 en `docs/owasp10llms-analisis.md`; detalle en `bitacora-dev.md` §4.
- **Siguiente paso**: grupo 7 (despliegue en el ECS + Vercel), **esperando indicaciones del equipo**. Luego, commit de la implementación y `/opsx:archive`.

## 1. El proyecto en una mirada

**InnovaBot**: chatbot RAG para consultas sobre la FISI (UNMSM). Dos interfaces — bot de Telegram (solo chats privados) y web mobile-responsive en Vercel — sobre un backend monolito modular FastAPI con pipeline: longitud → rate limit → regex → light LM (Ollama) → retrieval pgvector → LLM principal `deepseek-v4.1-flash` (MaaS, endpoint compatible con OpenAI) → validación anti-alucinación → respuesta con citas.

| Documento | Rol |
|---|---|
| `openspec/changes/add-fisi-rag-chatbot/` | Fuente de verdad: qué, cómo y tareas |
| `openspec/changes/harden-llm-security/` | Cambio de seguridad (OWASP LLM Top 10 2025) |
| `docs/owasp10llms-analisis.md` | Análisis de riesgos de seguridad LLM y mitigaciones |
| `AGENTS.md` | Reglas para agentes y equipo (KISS, secrets, convenciones) |
| `index-lima.html` | Prototipo de UI aprobado |
| `docs/bitacora.md` | Este documento |

## 2. Decisiones de arquitectura (ADR-lite)

| # | Decisión | Alternativas descartadas | Por qué | Documentado en |
|---|---|---|---|---|
| 1 | Fuentes: scraper de noticias FISI, PDFs del portal, FAQs curadas, portal central UNMSM | Solo portal FISI | Cobertura completa de consultas reales | `proposal.md` |
| 2 | Vector store: RDS PostgreSQL + pgvector | GeminiDB Vector | Un solo motor gestionado; metadata y boost de FAQs son SQL común; volumen no justifica motor dedicado | `design.md` §Almacén |
| 3 | LLM principal: `deepseek-v4.1-flash` vía Huawei MaaS, mediante su **endpoint compatible con OpenAI** (SDK `openai` con `base_url` de MaaS + API key de MaaS) *(ajustado en S1; originalmente DeepSeek 1017)* | Otros modelos del catálogo MaaS | Decisión del equipo; el endpoint OpenAI permite usar el SDK estándar y cambiar de modelo con una variable de entorno | `design.md` §Modelos |
| 4 | Light LM: Ollama local, `qwen2.5:3b-instruct-q4_K_M` | DeepSeek también; API externa (Gemini/GPT-mini) | MaaS no tiene modelos pequeños; local evita segundo vendor; 3B q4 es el mejor trade-off en CPU | `design.md` §Modelos |
| 5 | Embeddings: sentence-transformers `multilingual-e5-small` local | Ollama embeddings; API MaaS | Cero dependencia externa, corre en CPU, mismo modelo garantizado en ingesta y consulta | `design.md` §Modelos |
| 6 | Arquitectura: monolito modular | Microservicios; serverless | Un deployable simple de operar; límites de módulo permiten extraer servicios después | `design.md` §Backend |
| 7 | Ingesta: job batch, cron semanal + disparo manual | Scheduler en la app; servicio dedicado | Idempotente y recreable; su fallo no afecta al chat; recursos solo cuando corre | `design.md` §Backend |
| 8 | Despliegue: ECS + Docker Compose | FunctionGraph | Webhook de Telegram exige endpoint siempre disponible; un solo servidor, un solo modelo de operación | `design.md` §Despliegue |
| 9 | Frontend: React + TS + Vite + ESLint + Tailwind, publicado en Vercel | Servido por FastAPI | Vercel da HTTPS y dominio gratis; backend queda solo API con CORS | `design.md` §Frontend |
| 10 | TLS: Caddy + DuckDNS + Let's Encrypt | EIP directa; cert autofirmado; esperar dominio propio | Telegram exige HTTPS; Vercel no puede llamar HTTP (mixed content); LE no emite certs para IPs desnudas | `design.md` §Despliegue |
| 11 | Límites: 5 consultas/min, 30/hora, 500 chars; identidad anónima (user ID Telegram / session ID en localStorage web) | Rate limit por IP; ID efímera | NAT del campus compartiría IP; localStorage persiste sin login y es reseteable | spec `usage-limits` |
| 12 | Telegram: solo chats privados | Grupos con mención; grupos siempre | Sin ruido, sin contadores compartidos; grupos habilitables después | spec `telegram-ui` |
| 13 | Métricas: logs pasivos por consulta | Feedback 👍/👎 + métricas; nada | Cero UI extra; conteos diarios salen de logs que ya existen | spec `rag-answering` |
| 14 | Deploy de cambios: manual por SSH | GitHub Actions + SWR | Un servidor, equipo pequeño; CI/CD como mejora futura | `design.md` §Despliegue |
| 15 | Diseño UI: identidad FISI + rasgos del arte de la cultura Lima; light/dark con claro por defecto | Diseño simple azul/amarillo only | Homenaje a los habitantes de la huaca de San Marcos; aprobado por el equipo | spec `web-ui` |
| 16 | **KISS como principio rector** | — | La solución más simple que cumpla los specs; complejidad solo justificada por requisito o riesgo | `config.yaml`, `AGENTS.md` |
| 17 | **Hardening de seguridad LLM como cambio OpenSpec separado** (`harden-llm-security`) | Ignorar los riesgos / mezclarlos en `add-fisi` | El análisis OWASP LLM 2025 detectó riesgos Altos (inyección indirecta, consumo no acotado) y Medio-Altos (fuga de token, SSRF); se mitigan sin reabrir decisiones de producto | `docs/owasp10llms-analisis.md`, `openspec/changes/harden-llm-security/` |

## 3. Infraestructura Huawei Cloud (región LA-Santiago)

Provisionada por el equipo; verificada en esta sesión.

| Recurso | Detalle | Verificación |
|---|---|---|
| VPC `vpc-innova` | 192.168.0.0/16 | — |
| Subnet `subnet-innova` | 192.168.0.0/24, AZ Central | — |
| Security group `sg-innova` | Inbound: 80/443 abiertos; SSH restringido a la IP del equipo; 5432 solo desde la VPC | Reglas confirmadas en consola |
| ECS `ecs-innovabot` | 4 vCPU / 8 GB RAM, Ubuntu Server, EIP | Setup completado (§4) |
| RDS `rds-innovabot` | PostgreSQL 18, General 2 vCPU / 8 GB, Cloud SSD 60 GB, Single, AZ1, puerto 5432; **pgvector instalado**, DB `rag_fisi`; IP privada **192.168.0.168** | `nc` succeeded (§4.6) |
| DNS `innovabot.duckdns.org` | Apunta a la EIP (estática: configurado una vez, sin updater) | `nslookup` verificado (§5) |

## 4. Setup del ECS (Ubuntu Server) — paso a paso

Ejecutado como root/root-equivalent vía SSH. Pasos 1–5 ✅ completados y validados.

### 4.1 Base del sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo timedatectl set-timezone America/Lima   # el cron semanal de ingesta depende del horario local
```

### 4.2 Usuario de despliegue

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
ssh-copy-id deploy@<EIP>        # clave de acceso SSH (nada que ver con git: el repo es público, pull por HTTPS sin credenciales)
```

> Nota: la clave SSH es solo para *iniciar sesión* en el ECS. Para `git pull` del repo público no se configura nada — HTTPS anónimo.

### 4.3 Docker (repo oficial de Docker, no el paquete de Ubuntu)

```bash
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update && sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker deploy
sudo systemctl enable --now docker
```

### 4.4 Swap de 4 GB (red de seguridad de RAM)

El ECS (8 GB) correrá FastAPI + Ollama 3B (~4 GB) + sentence-transformers durante la ingesta (~1 GB extra). Riesgo documentado en `design.md`.

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 4.5 Endurecimiento de SSH

```bash
sudo tee /etc/ssh/sshd_config.d/hardening.conf > /dev/null <<'EOF'
PasswordAuthentication no
PubkeyAuthentication yes
EOF
sudo sshd -t                  # valida sintaxis (no debe imprimir nada)
sudo systemctl restart ssh
```

> Precaución aplicada: mantener la sesión viva y probar una conexión nueva antes de cerrar. Revertir: `sudo rm /etc/ssh/sshd_config.d/hardening.conf && sudo systemctl restart ssh`.

### 4.6 Verificación de conectividad al RDS

```bash
nc -zv 192.168.0.168 5432
# Connection to 192.168.0.168 5432 port [tcp/postgresql] succeeded!
```

> **Lección de la sesión**: el primer intento usó una IP equivocada (192.168.0.14) y devolvió *Connection refused*. Diagnóstico: **refused ≠ bloqueado por security group** (eso sería timeout por paquete descartado). Refused = el paquete llegó pero no había listener → IP incorrecta o instancia caída. Verificar siempre la IP privada en la consola del RDS.

## 5. DNS y TLS (DuckDNS)

1. Cuenta creada en **https://www.duckdns.org** iniciando sesión con GitHub.
2. Subdominio `innovabot` registrado → **`innovabot.duckdns.org`**.
3. EIP del ECS asignada en el campo "current ip" → **update domain**.
4. Verificación: `nslookup innovabot.duckdns.org` resuelve a la EIP. ✅

> Al ser la EIP estática, se configura una sola vez — no se necesita updater ni cron de DuckDNS. La tarea 7.2 usará este nombre en el Caddyfile para el Let's Encrypt automático.

## 6. Diseño de UI — iteraciones de la sesión

| Iteración | Archivo | Cambio | Resultado |
|---|---|---|---|
| v1 | `index.html` | Landing (gradiente azul) + chat, azul/amarillo | Base validada |
| v2 | `index.html` | Light/dark (claro por defecto), fondo blanco/negro, sin chips de temas, toggle persistente | Aprobado con ajuste pendiente |
| v3 | `index-lima.html` | Rasgos de la cultura Lima: banda de triángulos entrelazados, huaca escalonada con sol, greca, acento terracota `#b3502d` | **Aprobado — referencia oficial** |
| fix | `index-lima.html` | Avatar del chat con fondo blanco fijo en ambos temas (el sol amarillo desaparecía sobre el avatar amarillo en dark) | Integrado al spec como criterio de aceptación |

Tokens de identidad: azul `#003b71` (primario), amarillo `#ffc72c` (acento), terracota `#b3502d` (secundario, cerámica Lima). En claro, el subtítulo usa amarillo dorado `#c99400` por legibilidad sobre blanco.

## 7. Revisiones y mantenimiento del plan (S1)

### 7.1 Cambio del modelo principal

DeepSeek 1017 → **`deepseek-v4.1-flash`**, consumido mediante el **endpoint compatible con OpenAI** de Huawei MaaS: SDK `openai` de Python con `base_url` apuntando al endpoint de MaaS y la API key de MaaS; el nombre del modelo queda como variable de entorno.

Ajuste de forma aprovechado: el spec `rag-answering` se genericizó a "LLM principal" — la versión exacta del modelo es detalle de implementación y no debe vivir en un spec de comportamiento (este mismo cambio lo demostró). Se corrigieron de paso leftovers de GeminiDB que sobrevivieron a la migración a pgvector (en `proposal.md`, `design.md` y `tasks.md`).

### 7.2 Revisión de conflictos entre specs

Revisión cruzada de los 6 specs contra design y tasks. Hallazgos corregidos:

| # | Conflicto | Spec | Resolución |
|---|---|---|---|
| 1 | El log exigía registrarse "por cada consulta procesada" pero incluía el estado `limitada` (consultas que nunca llegan al pipeline) y exigía categoría para bloqueadas por regex (que nunca son clasificadas) | `rag-answering` | "por cada consulta **recibida**" + categoría "(cuando la consulta haya sido clasificada)" |
| 2 | El escenario de uso normal prometía procesamiento por el pipeline RAG para consultas dentro de límites — que el guardián puede igual bloquear | `usage-limits` | "ninguna es rechazada por los límites y continúan **hacia** el pipeline" |
| 3 | "Identificar de forma anónima" es incumplible con el user ID de Telegram (pseudónimo, no anónimo) | `usage-limits` | Requirement renombrada: "Identificación **del usuario sin login**" |
| 4 | El endpoint declaraba el estado `limitada` (design, tarea 5.1) sin escenario en el spec | `web-ui` | Escenario "Consulta con límite excedido" añadido |

Verificado **sin** conflictos: orden de chequeos (longitud → rate limit → regex → light LM), reparto del light LM entre capabilities (una llamada combinada según design), doble registro (auditoría del guardián vs métricas por consulta), prioridad de FAQs entre ingesta y retrieval, casos "contexto insuficiente" vs "sin resultados", estados del formato de respuesta, y alcance de Telegram a chats privados.

### 7.3 Hallazgos de implementación (S2)

Bugs reales que los tests de integración y la verificación de tareas cazaron durante el apply (grupos 1–6):

| # | Hallazgo | Dónde | Fix |
|---|---|---|---|
| 1 | psycopg adapta listas Python a `double precision[]`, pero el operador `<=>` de pgvector exige tipo `vector` — la búsqueda semántica fallaba con `UndefinedFunction` | `core/clientes.py` `buscar()` | Embedding en formato texto pgvector (`json.dumps`) + cast explícito `::vector` |
| 2 | En Linux, PyPI sirve torch **CUDA** por defecto: el build de Docker descargaba ~4 GB de paquetes `nvidia-*` para una GPU inexistente (proyecto CPU-only por diseño) | `docker/Dockerfile.backend` | `pip install torch --index-url .../whl/cpu` antes del resto: build de ~1h a ~1min |
| 3 | En CPUs híbridos de desarrollo (Intel Core Ultra: P+E+LPE cores), el auto-detect de threads de Ollama patina: generación a **0.17 tok/s** (5.9 s/token) vs ~15 tok/s esperados — cada token espera al thread que cayó en un core de baja potencia | `core/clientes.py` + settings | `OLLAMA_NUM_THREADS` opcional (6 = P-cores) en la petición; fijado en compose de desarrollo y conftest; sin definir en el ECS (vCPUs uniformes) |
| 4 | Tests de integración sin aislamiento: el test de retrieval dejaba filas y el de indexación asumía la tabla limpia | `tests/integration/test_indexar_pgvector.py` | TRUNCATE defensivo al inicio, como ya hacía el fixture de retrieval |

Lección transversal: **los tests de integración contra infraestructura real (pgvector, Ollama) cazaron 2 de los 4 bugs** que los unit tests con mocks no podían ver.

## 8. Seguridad del repo público

- **Auditoría pre-publicación**: cero UUIDs de Huawei Cloud en archivos (solo nombres de recursos), cero credenciales/tokens/IPs públicas. Nombres de recursos y CIDRs privados se mantienen por decisión del equipo (bajo riesgo: inaccesibles sin credenciales IAM).
- **`.gitignore`** ampliado: `.env*`, `*.pem`, `*.key`, `secrets/`, caches de Python/Node.
- **Gitleaks** activo desde S2 (tarea 1.6 verificada): `.gitleaks.toml` + hook versionado en `.githooks/pre-commit` (mecanismo único; el equipo lo activa con `git config core.hooksPath .githooks`, una vez por clon). Detecta un secreto sintético de prueba; el repo commiteable escanea limpio. `backend/.env` (credenciales reales en disco local) NO está allowlisted a propósito: gitleaks lo señala en escaneos completos, lo cual es correcto — no llega al repo porque `.gitignore` lo excluye y el hook solo escanea lo staged.
- **Regla fija** (`AGENTS.md` + `config.yaml`): credenciales solo por variables de entorno.
- **Git**: los commits los maneja exclusivamente el equipo (la herramienta de desarrollo no ejecuta comandos git). Mensaje sugerido para el commit inicial: `docs: add OpenSpec planning for FISI RAG chatbot`.

## 9. Cronología de sesiones

| Fecha | Sesión | Hitos |
|---|---|---|
| 2026-10-30 | **S1 — Planificación y entorno** | Propuesta OpenSpec completa (16 decisiones, 6 specs, 41 tareas) · Infra Huawei provisionada (ECS, RDS+pgvector, red) · Setup ECS (Docker, swap, SSH) · DuckDNS configurado · Prototipo Lima aprobado · Auditoría de seguridad del repo · AGENTS.md, KISS, gitleaks · Cambio de modelo principal a `deepseek-v4.1-flash` (endpoint OpenAI de MaaS) · Revisión de conflictos entre specs (4 corregidos) |
| 2026-10-31 | **S2 — Implementación local (grupos 1–6)** | 34/41 tareas: scaffolding + gitleaks activo · ingesta verificada contra pgvector real · guardián verificado contra Ollama real (JSON parseable en 8.8s) · pipeline RAG completo · SPA React verificada visualmente (Playwright, 390px, ambos temas) · Telegram · 110/110 tests en verde · 4 bugs cazados y corregidos (§7.3): cast pgvector, torch CUDA en Docker, threads en CPU híbrido, aislamiento de tests |

## 10. Convención para actualizar esta bitácora

1. **Al cerrar cada sesión de trabajo**: agregar una fila a la tabla de §9 con fecha, número de sesión y hitos.
2. **Secciones temáticas (§1–§8)**: actualizar los hechos que cambiaron (no reescribir la historia; los pasos completados llevan ✅ con fecha). El "Estado actual" se reescribe entero al cierre de cada sesión.
3. **Decisiones nuevas**: fila nueva en la tabla ADR de §2, numeración consecutiva.
4. **Comandos**: inline y completos si son nuevos; si corrigen un paso anterior, se añade la corrección junto al original (como la lección de §4.6), no se borra el original.
5. **Incidentes**: quedan en la sesión correspondiente con causa y solución.
6. **Revisiones del plan** (como la §7): los hallazgos se registran en tabla con su resolución; lo verificado-sin-conflicto se lista en una línea.

## Pendientes

- [x] Commit inicial del repo (equipo) — mensaje sugerido en §8.
- [x] `/opsx:apply`: grupos 1–6 en local (S2).
- [ ] Commit de la implementación (equipo) — gitleaks ya activo como pre-commit.
- [ ] Grupo 7 (despliegue en ECS + Vercel): **esperando indicaciones del equipo**.
- [ ] Tarea 7.4: crear tablas en `rag_fisi` e índice HNSW en la primera ingesta.
- [x] Cambio `harden-llm-security` aplicado (D3, 19/20 tareas; falta verificar 6.3 con Docker y rotar el token de Telegram al desplegar).
- [ ] `/opsx:archive` tras completar y revisar el grupo 7.
