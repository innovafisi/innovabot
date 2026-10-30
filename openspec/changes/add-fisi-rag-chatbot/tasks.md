# Tasks

## 1. Scaffolding del monorepo

- [ ] 1.1 Crear estructura `backend/` (paquete Python `app/` con `pyproject.toml`, FastAPI, ruff/pytest) y verificar que `pytest` corre con un test dummy en verde
- [ ] 1.2 Crear `frontend/` con `npm create vite@latest` (React + TypeScript), añadir ESLint y Tailwind CSS, y verificar que `npm run lint` y `npm run build` pasan con la plantilla inicial
- [ ] 1.3 Crear `docker/` con Dockerfile de backend, Dockerfile de frontend (build estático) y `docker-compose.yml` base; verificar que `docker compose build` completa sin errores
- [ ] 1.4 Definir la configuración por variables de entorno (MaaS: API key + endpoint + modelo, RDS, Telegram, Ollama) con un módulo de settings tipado y verificar que la app falla con mensaje claro si falta una variable obligatoria
- [ ] 1.5 Añadir el servicio Ollama al docker-compose de desarrollo (volumen persistente, `num_parallel: 1`) y un script que descargue el modelo light LM (`ollama pull qwen2.5:3b-instruct-q4_K_M`); verificar que `GET /api/tags` de Ollama lista el modelo descargado
- [ ] 1.6 Configurar gitleaks (`.gitleaks.toml` + pre-commit hook, y paso de escaneo si se añade CI) para el repo público; verificar que detecta un secreto de prueba (ej. un token falso en un archivo temporal) y que un commit normal sin secretos pasa sin bloquear

## 2. Ingesta de conocimiento (spec: knowledge-ingestion)

- [ ] 2.1 Implementar el scraper de noticias del portal FISI (título, contenido, fecha, URL) con selectores centralizados y registro de errores por página; verificar con un test contra HTML fixture que extrae los campos y con la ejecución real que registra fallos sin detenerse
- [ ] 2.2 Implementar la descarga y extracción de PDFs del portal (pdfplumber) con chunking por secciones y solapamiento; verificar con un test sobre un PDF fixture que los fragmentos preservan secciones y que un PDF ilegible queda registrado y excluido
- [ ] 2.3 Implementar la carga de FAQs curadas desde el archivo Markdown del repo; verificar con un test que cada Q&A genera un fragmento con metadata `tipo=faq` y que re-ejecutar no duplica entradas
- [ ] 2.4 Implementar el scrapeo de las secciones configurables del portal central UNMSM (lista en YAML); verificar con un test que solo se ingieren las secciones configuradas
- [ ] 2.5 Implementar el cálculo de hash de contenido (deduplicación por SHA-256 normalizado) y la invalidación de versiones obsoletas por `source_url`; verificar con un test que una re-ingesta sin cambios no inserta duplicados y que un documento actualizado reemplaza al anterior
- [ ] 2.6 Implementar la generación de embeddings (sentence-transformers `multilingual-e5-small`) y la indexación en RDS PostgreSQL con pgvector (tabla con columna `vector` e índice HNSW, metadata `{tipo, url, titulo, fecha}`); verificar con un test de integración (base de datos de prueba) que un fragmento indexado es recuperable por búsqueda semántica y filtrable por metadata
- [ ] 2.7 Documentar la ejecución de la ingesta (`python -m app.ingest`, variables y YAML de secciones) en `backend/README.md` y verificar que los comandos documentados corren tal cual

## 3. Guardián de entrada (spec: prompt-injection-guard)

- [ ] 3.1 Implementar el filtro regex de patrones de prompt injection (override de instrucciones, revelar system prompt, jailbreaks) con patrones anclaados; verificar con tests unitarios que bloquea los mensajes de inyección canónicos y no bloquea consultas legítimas con palabras aisladas sospechosas
- [ ] 3.2 Implementar la llamada al light LM (Ollama local, `format: json`, temperatura 0) para guard + clasificación + reescritura en una única petición con salida JSON `{safe, category, rewritten_query}`; verificar con tests (mock del light LM) que una instrucción encubierta se marca insegura y una consulta académica queda segura y clasificada, y con una prueba de integración contra Ollama real que el JSON se parsea correctamente
- [ ] 3.3 Implementar los mensajes estándar de rechazo y fuera de alcance en español, y la derivación temprana que evita invocar retrieval y LLM principal; verificar con un test del orquestador que una consulta bloqueada no genera llamadas al LLM principal ni a la base de datos vectorial
- [ ] 3.4 Implementar el registro de intentos bloqueados (motivo, timestamp, interfaz) sin datos personales; verificar con un test que cada bloqueo deja exactamente un registro con su motivo

## 4. Pipeline de respuesta RAG (spec: rag-answering)

- [ ] 4.1 Implementar la recuperación semántica top-k en PostgreSQL (pgvector) con boost de prioridad para fragmentos `tipo=faq`; verificar con un test de integración que una consulta con FAQ correspondiente la recupera con prioridad
- [ ] 4.2 Implementar la generación con el LLM principal (`deepseek-v4.1-flash` vía el endpoint compatible con OpenAI de MaaS: SDK `openai` con `base_url` de MaaS y API key de MaaS) usando solo el contexto recuperado (system prompt restrictivo, temperatura baja, español); verificar con tests (mock del LLM) que el prompt incluye exclusivamente los fragmentos y la instrucción de citar fuentes
- [ ] 4.3 Implementar la validación anti-alucinación con el light LM y la política de reintento (1 regeneración con feedback, luego mensaje estándar); verificar con tests (mocks) que una respuesta no respaldada no se entrega tal cual y que una respaldada sí
- [ ] 4.4 Implementar el ensamblado de citas (título + URL de los fragmentos usados) y el mensaje estándar cuando no hay resultados relevantes; verificar con un test end-to-end del pipeline (mocks de LLMs, RDS de prueba) que la salida incluye citas correctas y el estado `ok|bloqueada|sin_resultados`
- [ ] 4.5 Documentar el contrato del pipeline (entrada/salida, estados) en `backend/README.md` y verificar con un ejemplo ejecutable que el pipeline responde tal como está documentado
- [ ] 4.6 Implementar el módulo de límites de uso en `core/` (ventana deslizante en memoria: 5/min y 30/hora por identidad, rechazo de consultas >500 caracteres sin truncar, límites por variables de entorno `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_HOUR`, `MAX_QUERY_CHARS`); verificar con tests unitarios que la 6ª consulta en un minuto y la 31ª en la hora se rechazan con tiempo de reintento, que una consulta de 500 caracteres pasa y una de 501 se rechaza, y que los límites se aplican independientemente por identidad (user ID de Telegram / session ID web)
- [ ] 4.7 Implementar el log estructurado por consulta en el orquestador (`{interfaz, categoria, estado, latencia_ms, timestamp}`, sin contenido de la consulta ni datos personales); verificar con un test que una consulta ok y una bloqueada dejan cada una su registro con el estado correcto

## 5. API web y frontend React (spec: web-ui)

- [ ] 5.1 Implementar `POST /api/chat` en FastAPI (validación de entrada, formato `{reply, citas, estado}` con estado `limitada` y HTTP 429 al exceder límites, CORS restringido al origen de Vercel por variable de entorno, lectura del header `X-Session-ID` como identidad para el rate limit); verificar con tests de API que una consulta válida devuelve el formato completo, una bloqueada devuelve el mensaje estándar, una sin session ID o con límite excedido devuelve 429 con estado `limitada`, y una petición con Origin ajeno recibe el CORS correcto
- [ ] 5.2 Implementar la SPA en React + TypeScript con dos vistas: pantalla de inicio (nombre del bot, propósito, botón para comenzar a chatear) y vista de chat (hilo de conversación, campo de envío, indicador de espera y renderizado de citas), tomando como referencia el prototipo `index-lima.html` de la raíz; verificar con `npm run lint`, `npm run build` y una prueba manual documentada de envío/respuesta
- [ ] 5.3 Implementar la identidad visual (tokens de color en la config de Tailwind: azul primario, amarillo acento, terracota secundario) con los rasgos del arte de la cultura Lima (banda de triángulos entrelazados, logotipo de huaca escalonada con sol sobre fondo blanco en ambos temas, greca escalonada), el modo claro/oscuro con claro por defecto, toggle y preferencia persistente en localStorage, y el layout mobile-responsive (mobile-first, sin scroll horizontal, ancho máx. 720px); verificar con una revisión en viewport de móvil (DevTools) que no hay scroll horizontal, que los colores y motivos siguen los tokens en ambos temas, que el icono del bot es visible en claro y oscuro, y que el toggle alterna todas las vistas
- [ ] 5.4 Añadir manejo de errores y estados de la UI (bloqueada, limitada, sin resultados, fallo de red) con mensajes amigables; verificar con tests de componentes que cada estado renderiza su mensaje correcto
- [ ] 5.5 Implementar la session ID anónima en el frontend (UUID v4 generado en la primera carga, persistido en localStorage, enviado como header `X-Session-ID` en cada consulta) y un contador de caracteres visible con aviso al acercarse a los 500; verificar con tests de componentes que la ID persiste entre recargas y que el aviso aparece antes de superar el límite

## 6. Bot de Telegram (spec: telegram-ui)

- [ ] 6.1 Implementar el endpoint de webhook `POST /telegram/webhook/{token}` con verificación del secret token de Telegram; verificar con tests que una petición autenticada se procesa y una sin secret se rechaza con 401/403
- [ ] 6.2 Implementar el flujo de respuesta al mensaje (consulta → pipeline RAG → respuesta con citas en el mismo chat) usando el mismo orquestador que la web, con rate limit contra el user ID de Telegram y rechazo de consultas >500 caracteres; verificar con un test (mock de la API de Telegram) que ante un update legítimo se envía exactamente una respuesta al chat de origen, que la 6ª consulta en un minuto recibe el mensaje de límite, y que una consulta demasiado larga recibe el aviso de acortar
- [ ] 6.3 Implementar los comandos `/start` y `/help` con mensajes de bienvenida y temas atendidos; verificar con tests que cada comando responde con su mensaje y no entra al pipeline RAG
- [ ] 6.4 Implementar el mensaje amigable ante fallos del pipeline y el registro del error para el equipo; verificar con un test (pipeline que lanza excepción) que el usuario recibe el mensaje amigable y el error queda logueado
- [ ] 6.5 Implementar el filtro de alcance a chats privados (descartar updates de grupos antes del pipeline); verificar con tests que un update de grupo no genera respuesta ni consume pipeline ni rate limit, y que un update privado se procesa con normalidad

## 7. Despliegue en Huawei Cloud (ECS + Docker)

- [ ] 7.1 Finalizar `docker-compose.yml` de producción (app + ollama + caddy, `restart: always`, solo puertos 80/443 publicados en la EIP, app y ollama internos) y el cron semanal de ingesta (`docker compose run ingest`); verificar que el compose arranca en el ECS `ecs-innovabot` y que el healthcheck del endpoint responde a través de Caddy
- [ ] 7.2 Configurar el DNS gratuito apuntando a la EIP y el Caddyfile con Let's Encrypt automático; verificar que `https://<dns>/api/chat` responde con certificado válido y que el security group `sg-innova` solo permite 80/443 y SSH
- [ ] 7.3 Descargar el modelo light LM en el volumen de Ollama del ECS (`qwen2.5:3b-instruct-q4_K_M`) y verificar con una consulta real de guardián que responde JSON válido dentro de la latencia objetivo
- [ ] 7.4 Configurar el acceso del backend a `rds-innovabot` (PostgreSQL 18, base `rag_fisi`, pgvector ya instalado; regla del 5432 en `sg-innova` solo desde la VPC), crear las tablas con el índice HNSW, cargar credenciales MaaS como variables en el ECS y ejecutar la primera ingesta completa; verificar que el índice contiene fragmentos de las 4 fuentes (noticias, PDFs, FAQs, portal central)
- [ ] 7.5 Crear el bot con BotFather, registrar el webhook con `setWebhook` (URL con TLS + secret token) y verificar end-to-end: mensaje real por Telegram recibe respuesta con citas
- [ ] 7.6 Desplegar el frontend en Vercel (carpeta `frontend/`, variable de entorno con la URL del backend) y verificar la web en producción desde móvil y escritorio: chat funcional contra el backend, colores FISI y sin scroll horizontal; documentar la URL de verificación en `backend/README.md`
- [ ] 7.7 Documentar en `backend/README.md` el procedimiento de despliegue manual por SSH (git pull / docker pull + `docker compose up -d`) y el disparo manual de la ingesta (`docker compose run ingest`); verificar que los comandos documentados ejecutan tal cual en el ECS

## Workflow follow-up

- Archive the change after the project's review requirements are satisfied.
- Verify the archived result.
