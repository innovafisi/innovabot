# Design

## Context

Proyecto greenfield (repo `innovabot` vacío, sin código previo). Se construye un chatbot RAG sobre información de la FISI (UNMSM) con dos interfaces (Telegram y web) y servicios de Huawei Cloud. Decisiones de producto ya tomadas con el usuario: fuentes (noticias del portal FISI, PDFs del portal, FAQs curadas, portal central UNMSM), RDS PostgreSQL con pgvector como vector store, DeepSeek 1017 vía Huawei MaaS como LLM principal, un light LM con roles de guardián/clasificador/reescritor/validador, y frontend en React con TypeScript, ESLint, Vite y Tailwind CSS publicado en Vercel. MaaS no ofrece modelos pequeños, por lo que el light LM es un modelo local vía Ollama en el propio ECS (solo CPU + RAM, Ubuntu Server) y los embeddings se generan local con sentence-transformers. La arquitectura del backend es un monolito modular y la ingesta permanece como job batch bajo cron.

Infraestructura ya provisionada en Huawei Cloud (región LA-Santiago): VPC `vpc-innova` (192.168.0.0/16), subnet `subnet-innova` (192.168.0.0/24, AZ Central), security group `sg-innova`, y ECS `ecs-innovabot` (4 vCPU / 8 GB RAM) con EIP.

## Goals / Non-Goals

**Goals:**

- **KISS como principio rector**: la solución más simple que cumpla los specs; complejidad solo cuando un requisito o un riesgo documentado la exija.
- Arquitectura simple de operar: pocos componentes contenerizados en un solo ECS.
- Pipeline RAG con defensa en capas (regex + light LM) y validación anti-alucinación.
- Ingesta idempotente y re-ejecutable (scraper + PDFs + FAQs + portal central).
- Ambas UIs compartiendo un único pipeline de respuesta.

**Non-Goals:**

- Autenticación de usuarios finales (chat público).
- Streaming de respuestas token a token (MVP: respuesta completa).
- Historial de conversación persistente entre sesiones o multi-turno con memoria.
- Panel de administración de FAQs (se editan como archivos en el repo).

## Decisions

### Estructura del repo (monorepo)

```
innovabot/
├── backend/            # Python: FastAPI, pipeline RAG, ingesta, worker Telegram
├── frontend/           # React + TypeScript + Vite + ESLint + Tailwind CSS
├── docker/             # Dockerfiles y docker-compose.yml
└── openspec/
```

**Alternativa descartada**: repos separados por componente — más fricción para un equipo pequeño y un solo despliegue.

### Backend: monolito modular (un servicio FastAPI, tres entrypoints)

**Arquitectura: monolito modular.** Un solo deployable con límites de módulo explícitos — cada módulo se comunica por interfaces internas (imports de paquete), sin estado compartido oculto, de modo que cualquiera pueda extraerse a un servicio independiente si escala:

```
backend/app/
├── core/         # settings, logging, clientes (MaaS, Ollama, GeminiDB)
├── ingestion/    # scraper noticias, pdfs, faqs, portal central, chunking, indexación
├── guard/        # regex + light LM (guardián, clasificación)
├── rag/          # reescritura, retrieval, generación, validación, citas
└── interfaces/   # api web (/api/chat) + webhook Telegram
```

**Alternativas descartadas**: microservicios desde el inicio (multiplica contenedores, redes y monitoreo para un equipo pequeño y un MVP) y serverless (ya descartado en la decisión de despliegue).

Un único código Python con tres formas de ejecutarse (mismo contenedor, comandos distintos):

1. `uvicorn` — API web: sirve el endpoint de chat (`POST /api/chat`) con CORS habilitado para el origen del frontend en Vercel. El frontend ya no se sirve desde el backend: vive en Vercel.
2. Mismo `uvicorn` — endpoint de webhook de Telegram (`POST /telegram/webhook/{token}`), protegido con el secret token de Telegram (header `X-Telegram-Bot-Api-Secret-Token`).
3. `python -m app.ingest` — pipeline de ingesta, ejecutado bajo cron del host o contenedor efímero.

**Racional**: el webhook de Telegram exige un endpoint HTTP siempre disponible; encaja naturalmente en la misma app FastAPI sin un worker separado. La ingesta es un job batch, no un servicio.

**Alternativa descartada**: FunctionGraph para el webhook — mezjaría dos modelos de operación sin beneficio en un solo ECS.

### Pipeline de respuesta (por mensaje)

```
Mensaje → [Longitud ≤ 500 chars] → [Rate limit 5/min · 30/hora]
        → [Regex guard] → [Light LM: guard + clasificación]
        → (bloqueado/fuera de alcance → mensaje estándar)
        → [Light LM: reescritura de consulta]
        → [Retrieval pgvector top-k]
        → (sin resultados → mensaje estándar)
        → [DeepSeek 1017: generación con contexto]
        → [Light LM: validación anti-alucinación]
        → Respuesta + citas
```

- Los chequeos van del más barato al más caro: longitud y rate limit son puro cómputo local; el regex corre siempre antes que cualquier modelo (coste cero, latencia cero).
- Guard + clasificación + reescritura usan el mismo light LM en una sola llamada combinada cuando sea posible (un prompt con salida JSON: `{"safe": bool, "category": str, "rewritten_query": str}`) para reducir latencia de 2 llamadas a 1.
- La validación anti-alucinación es una segunda llamada al light LM, solo sobre la respuesta generada.
- Si la validación falla, se reintenta la generación una vez con feedback; si vuelve a fallar, se entrega el mensaje estándar de "información no disponible".

### Ingesta y chunking

- **Noticias FISI**: scraper HTTP del listado de noticias (solo noticias, según decisión del usuario); extracción de título/contenido/fecha/URL. Selectores tolerantes a cambios del portal + registro de errores por página.
- **PDFs**: descarga desde enlaces del portal; extracción con `pdfplumber` (texto + estructura); chunking por secciones con solapamiento (~200 tokens).
- **FAQs curadas**: archivo en el repo (formato Markdown con estructura pregunta/respuesta); cada Q&A es un fragmento único con metadata `tipo=faq` y boost de prioridad en retrieval.
- **Portal central UNMSM**: lista de secciones configurables (YAML de configuración); scrapeo acotado a esas secciones.
- **Deduplicación**: hash del contenido (SHA-256 normalizado) como ID del fragmento; re-ingesta = upsert por hash; documento actualizado → nuevo hash → el fragmento anterior se marca obsoleto por su `source_url`.
- **Embeddings**: se generan en la ingesta con sentence-transformers local (ver "Modelos") y se insertan en RDS PostgreSQL (pgvector) con metadata: `{tipo, url, titulo, fecha}`.

### Almacén vectorial: RDS PostgreSQL + pgvector

- **Decisión**: RDS for PostgreSQL de Huawei Cloud con el plugin `pgvector`, en la misma VPC `vpc-innova` (acceso privado desde el ECS, sin exponer el puerto 5432 a internet).
- **Instancia ya provisionada**: `rds-innovabot` — PostgreSQL 18, tipo General-purpose 2 vCPU / 8 GB, Cloud SSD 60 GB, instancia Single, AZ1, puerto 5432, VPC `vpc-innova` / subnet `subnet-innova` / SG `sg-innova`, billing pay-per-use. La extensión `pgvector` ya está instalada y la base de datos `rag_fisi` creada.
- **Racional**: un solo motor gestionado para vectores y metadata — el filtrado por metadata (`tipo`, `fecha`) y el boost de FAQs son consultas SQL comunes, la operativa es la de una base de datos familiar (backups, restore) y el índice es recreable re-ejecutando la ingesta. Con pgvector se usa índice HNSW/IVFFlat sobre la columna `vector`.
- **Nota de red**: `sg-innova` debe permitir el 5432 únicamente desde dentro de la VPC (el ECS), nunca desde internet.
- **Alternativa descartada**: GeminiDB Vector — especializado y escalable, pero agrega un motor propietario más que operar cuando el volumen (noticias + PDFs de una facultad) no lo justifica.

### Límites de uso e identidad anónima

- **Identidad sin login**: Telegram entrega su user ID nativo con cada mensaje — el rate limit usa ese ID. La web genera un UUID v4 en la primera carga, lo persiste en `localStorage` y lo envía con cada consulta en el header `X-Session-ID`; el backend hace rate limit contra ese valor. Anónimo, persiste entre visitas y el usuario puede borrarlo para empezar de cero.
- **Límites**: 5 consultas/minuto y 30/hora por usuario (ventana deslizante), 500 caracteres por consulta (se rechaza con mensaje pidiendo acortar — no se trunca). Valores por variable de entorno: `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_HOUR`, `MAX_QUERY_CHARS`.
- **Orden de chequeos por mensaje** (del más barato al más caro): longitud → rate limit → regex guard → light LM. Todo lo rechazado en etapas tempranas no consume llamadas LLM.
- **Implementación**: contadores de ventana deslizante **en memoria del proceso** (módulo de `core/`, usado por ambas interfaces). Al haber un solo contenedor `app`, es correcto y barato. Trade-off aceptado: los contadores se reinician si se reinicia el contenedor — para mitigación de abuso es tolerable. Si en el futuro hay varias réplicas o se necesita persistencia, se migra a Redis o a una tabla en el RDS sin cambiar la interfaz del módulo.
- **Respuesta al exceder el límite**: mensaje estándar en español con el tiempo de espera; en la web el endpoint responde 429 con el mismo formato `{reply, citas, estado}` (estado `limitada`) para que el frontend lo renderice como mensaje del bot.

### Alcance del bot de Telegram

- **Solo chats privados (1:1)**: el worker descarta los updates de grupos antes de entrar al pipeline — sin respuesta, sin consumo de rate limit ni de llamadas LLM. Evita ruido en canales de la facultad y contadores compartidos por grupo. Habilitar grupos (con mención) queda como mejora futura si el equipo lo pide.

### Observabilidad (MVP)

- **Logs pasivos, sin feedback en UI**: registro estructurado por consulta en el orquestador (única pieza por la que pasan ambas interfaces): `{interfaz, categoria, estado, latencia_ms, timestamp}`. Sin contenido de la consulta ni datos personales. Los conteos diarios (consultas por estado/categoría/interfaz) se extraen de esos logs; los bloqueos del guardián ya tienen su propio registro (spec `prompt-injection-guard`).
- **Alternativa descartada**: botones 👍/👎 — suman UI, endpoint y almacenamiento al MVP; se puede añadir después sobre la session ID / user ID ya existentes.

### Modelos (Huawei MaaS + Ollama local)

- **LLM principal**: DeepSeek 1017 vía MaaS (generación con contexto RAG, temperatura baja).
- **Light LM**: modelo local vía Ollama en el mismo ECS (MaaS no ofrece modelos pequeños). Sin GPU, la elección prioriza calidad en CPU y consumo de RAM:
  - **Recomendado**: `qwen2.5:3b-instruct-q4_K_M` (~2 GB en disco, ~3–4 GB RAM en ejecución). Buen español, buen seguimiento de instrucciones y JSON fiable — clave para la salida estructurada del guardián. En 4 vCPU genera ~10–20 tok/s: suficiente para los prompts cortos de guard/validación.
  - **Plan B** si el ECS queda justo de RAM: `llama3.2:1b` (~1.3 GB, ~2 GB RAM), más rápido pero más débil validando.
  - **Solo con ECS de 16 GB**: `qwen2.5:7b-instruct-q4_K_M` (~4.7 GB), mejor calidad de validación anti-alucinación.
  - Configuración: cuantización q4_K_M, `num_parallel: 1` (evita disputa de RAM con la generación), `format: json` en las llamadas del guardián, temperatura 0.
  - El código accede al light LM tras la misma interfaz de cliente LLM de `core/`, para poder cambiar de modelo (o volver a un API gestionado) sin tocar el pipeline.
- **Embeddings**: **sentence-transformers local** en el backend (modelo `intfloat/multilingual-e5-small`, ~470 MB, excelente en español). Corre en la CPU del ECS sin GPU y solo consume RAM durante la ingesta; al vivir dentro del backend, la ingesta y las consultas usan garantizadamente el mismo modelo. **Alternativas descartadas**: embeddings vía Ollama (suma RAM al contenedor y mezcla cargas de ingesta con el guardián en tiempo real) y API de MaaS (depende de disponibilidad en LA-Santiago y añade latencia de red).

### Frontend web

- **React + TypeScript + Vite + ESLint + Tailwind CSS** (decisiones del usuario), publicado en **Vercel**.
- SPA de dos vistas: **pantalla de inicio** (nombre del bot, propósito, botón para comenzar a chatear) y **chat** (cabecera con identidad FISI, hilo de conversación, campo de entrada). El prototipo estático de validación de diseño aprobado vive en `index-lima.html` en la raíz del repo (`index.html` queda como versión previa sin arte Lima).
- Colores: azul institucional primario (base `#003B71`-ish, ajustable), amarillo acento (`#FFC72C`-ish) y terracota como acento secundario (`#B3502D`, el rojo-naranja de la cerámica Lima, usado con moderación: sol del logo, greca, borde de citas y línea de la banda); definidos como tokens en la config de Tailwind (`theme.extend.colors`).
- **Rasgos del arte de la cultura Lima** (aprobados por el usuario, en honor a los habitantes de la huaca de San Marcos): banda de triángulos entrelazados con línea terracota (franja superior del inicio y bajo la cabecera del chat), logotipo de huaca escalonada con sol triangular y líneas de adobe (idéntico en el avatar del chat, sobre fondo blanco fijo en ambos temas para que el sol nunca se funda con el fondo), greca escalonada bajo el subtítulo, y línea de crédito "Diseño inspirado en el arte de la cultura Lima" en el pie del inicio.
- **Modo claro y oscuro, claro por defecto**: tokens por tema. Claro: fondo blanco, título azul oscuro, subtítulo amarillo, descripción azul. Oscuro: fondo negro, título y descripción blancos, subtítulo amarillo. El toggle alterna entre temas, la preferencia persiste en localStorage junto a la session ID, y el chat se adapta (burbujas, composer y citas) a ambos.
- Mobile-first: layout fluido, sin scroll horizontal, ancho máximo ~720px en escritorio.
- **Hosting**: Vercel da HTTPS y dominio al frontend (ej. `innovabot.vercel.app`). El backend NO sirve los estáticos: FastAPI habilita CORS únicamente para el origen de Vercel.
- Llamada a `POST https://<backend>/api/chat` con `{ "query": string }` más el header `X-Session-ID` (UUID en localStorage, generado en la primera carga); respuesta `{ "reply": string, "citas": [{titulo, url}], "estado": "ok|bloqueada|sin_resultados|limitada" }`. La URL del backend se configura como variable de entorno del frontend en Vercel.

### Despliegue (Huawei Cloud ECS + Docker, región LA-Santiago)

Infraestructura ya creada: VPC `vpc-innova` (192.168.0.0/16), subnet `subnet-innova` (192.168.0.0/24, AZ Central), security group `sg-innova`, ECS `ecs-innovabot` (4 vCPU / 8 GB RAM, sin GPU) con EIP.

- **Docker Compose en el ECS** con cuatro piezas:
  - `app` (FastAPI: API web + webhook de Telegram) — **sin puertos publicados al host**; solo accesible dentro de la red interna de Docker.
  - `ollama` (light LM, volumen persistente para el modelo, `num_parallel: 1`) — igualmente interno.
  - `caddy` (reverse proxy) — único contenedor con puertos publicados: **80 y 443** en la EIP. Termina TLS con Let's Encrypt automático y proxya a `app`.
  - Ingesta como job programado: **cron semanal** del host que lanza `docker compose run ingest`, más un disparo manual documentado (`docker compose run ingest` por SSH) para cuando el equipo publique algo urgente (ej. aviso de matrícula).
- **TLS**: DNS gratuito (ej. `innovabot.duckdns.org`) apuntando a la EIP; Caddy emite y renueva el certificado Let's Encrypt contra ese nombre. Sirve tanto a `/api/chat` (evita mixed content desde Vercel) como al webhook de Telegram. Si luego hay subdominio institucional, se cambia una línea de Caddyfile.
- **Security group `sg-innova`**: inbound solo 80, 443 y SSH restringido; el 5432 del RDS nunca se expone a internet (el RDS vive en `vpc-innova` y el ECS accede por la red privada).
- **RDS PostgreSQL** en la misma VPC, con `pgvector` habilitado; credenciales por variables de entorno.
- **Frontend**: deploy en Vercel desde el repo (carpeta `frontend/`), con la URL del backend como variable de entorno.
- **Despliegue de cambios del backend**: manual por SSH — `git pull` (o `docker pull` de la imagen) y `docker compose up -d` en el ECS; procedimiento documentado en `backend/README.md`. CI/CD automatizado (GitHub Actions + SWR) queda como mejora futura.
- Sizing validado: 4 vCPU / 8 GB RAM alcanza para FastAPI + Ollama `qwen2.5:3b` + sentence-transformers durante la ingesta (el modelo de embeddings ~1 GB de RAM se carga solo en el proceso de ingesta).
- Configuración por variables de entorno: credenciales MaaS, conexión GeminiDB, token del bot de Telegram, secret del webhook.
- Telegram: webhook registrado vía `setWebhook` apuntando a `https://<dominio>/telegram/webhook/<token-secreto>`; requiere dominio + TLS (nginx como reverse proxy en el mismo compose o certificado en el balanceador).

## Risks / Trade-offs

- [El portal FISI cambia su HTML y rompe el scraper] → Selectores centralizados y tolerantes; la ingesta registra fallos por página sin detenerse; alerta si una ejecución ingiere 0 noticias.
- [4 llamadas LLM por mensaje aumentan latencia] → Light LM pequeño y rápido; guard+clasificación+reescritura combinados en una llamada; validación solo sobre respuestas generadas. Latencia objetivo < 10s por respuesta.
- [Ollama en CPU añade segundos por llamada y compite por RAM con el resto] → Modelo 3B cuantizado q4_K_M, prompts cortos, `num_parallel: 1` y sizing de ECS con cabeza de RAM; la interfaz de cliente permite migrar el light LM a un API gestionado sin tocar el pipeline.
- [El modelo 3B se equivoca en guard/validación (falsos bloqueos o alucinaciones aprobadas)] → Regex como primera capa objetiva; mensajes estándar ante duda del guardián; banco de casos de prueba de inyección/legítimos para evaluar el modelo antes de cambiar de flavor.
- [PDFs escaneados (imágenes) sin texto extraíble] → `pdfplumber` los detecta como vacíos; quedan registrados y excluidos. OCR fuera de alcance (Non-Goal).
- [Regex genera falsos positivos bloqueando consultas legítimas] → Patrones anclaados a instrucciones (no palabras sueltas); el light LM actúa como segunda opinión antes de bloquear.
- [Prompt injection evoluciona más rápido que los patrones] → Defensa en capas + logs de auditoría para iterar patrones; el system prompt de DeepSeek restringe a contexto recuperado.
- [Costo de RDS y MaaS en producción] → Empezar con la instancia RDS mínima; monitorear tokens consumidos; FAQs curadas reducen llamadas al LLM para consultas frecuentes.
- [Un solo ECS = punto único de fallo] → Aceptado para MVP; reinicio automático con `restart: always` y snapshots del ECS.
- [pgvector no disponible en la versión de RDS elegida] → Verificar al provisionar que el motor soporta el plugin (PostgreSQL 14+); si no, subir de versión la instancia antes de la primera ingesta — el índice es recreable.
- [sentence-transformers compite por RAM durante la ingesta con Ollama en un ECS de 8 GB] → La ingesta corre por cron en horario de baja demanda; el modelo de embeddings se descarga de memoria al terminar el proceso.
- [DNS gratuito (DuckDNS) poco fiable o con latencia de propagación] → Solo afecta la emisión/renovación del certificado; Caddy reintenta. Migrar a subdominio propio cuando exista es un cambio de una línea.
- [CORS mal configurado bloquea la web] → El origen permitido es una variable de entorno; test de integración que simula el origen de Vercel en el pipeline de CI.
- [Un secreto (token, contraseña, `.env`) se commitea por descuido en un repo público] → `.gitignore` cubre `.env`/claves/`secrets/`; **gitleaks** configurado como pre-commit hook y paso de CI que escanea antes de cada push; regla de solo-variables-de-entorno documentada en `AGENTS.md`. Si gitleaks marca algo, la credencial se rota antes de seguir.

## Migration Plan

Despliegue inicial sin usuarios (greenfield), por lo tanto sin migración de datos. La red (VPC/subnet/SG), el ECS y el RDS `rds-innovabot` (PostgreSQL 18 + pgvector, base `rag_fisi`) ya están provisionados:

1. Crear credenciales MaaS y las tablas en `rag_fisi` (fragmentos + índice HNSW).
2. Configurar el DNS gratuito apuntando a la EIP del ECS.
3. Crear el bot con BotFather; obtener token y secret del webhook.
4. Desplegar el compose en el ECS (app + ollama + caddy); descargar el modelo light LM; ejecutar la primera ingesta completa.
5. Registrar el webhook de Telegram contra el dominio del backend y desplegar el frontend en Vercel con la URL del backend configurada.
6. Validar end-to-end ambas UIs.
7. Rollback: versión anterior de la imagen Docker; el índice en RDS es recreable desde cero re-ejecutando la ingesta.
