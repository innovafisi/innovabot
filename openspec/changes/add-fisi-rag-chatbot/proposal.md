# Proposal

## Why

Los estudiantes y postulantes de la Facultad de Ingeniería de Sistemas e Informática (FISI) de la UNMSM no tienen una vía rápida para resolver sus consultas académicas: la información está dispersa en el portal web (sistemas.unmsm.edu.pe), en PDFs de planes de estudio y reglamentos, y en el portal central de la UNMSM. Un chatbot RAG centraliza ese conocimiento y responde en lenguaje natural, con citas a las fuentes, 24/7 desde Telegram o la web.

## What Changes

- **Pipeline de ingesta de conocimiento**: scraper de noticias del portal FISI, descarga y extracción de texto de PDFs del portal (planes de estudio, reglamentos), FAQs curadas manualmente y contenido relevante del portal central UNMSM; con chunking, embeddings (sentence-transformers local) e indexación en RDS PostgreSQL con el plugin pgvector.
- **Pipeline de respuesta RAG**: recuperación semántica en GeminiDB + generación con DeepSeek 1017 vía Huawei MaaS, con respuestas en español citando las fuentes.
- **Guardián de entrada**: filtro regex + light LM que bloquea prompt injection, clasifica la consulta y decide si responder o derivar.
- **Reescritura de consultas**: light LM que convierte preguntas coloquiales en consultas óptimas para retrieval.
- **Validación de respuestas**: light LM que verifica que la respuesta de DeepSeek esté respaldada por los fragmentos recuperados (anti-alucinación) antes de enviarla.
- **Límites de uso sin login**: identificación anónima por usuario (user ID nativo de Telegram; session ID en localStorage para la web), con máximo 5 consultas por minuto y 30 por hora por usuario, y máximo 500 caracteres por consulta.
- **Bot de Telegram**: bot creado con BotFather, atendido por un worker vía webhook.
- **Web de chat**: página mobile-responsive de diseño simple con Tailwind CSS, azul como color primario y amarillo como acento (colores de la facultad), publicada en Vercel.
- **Despliegue**: Huawei Cloud ECS + Docker (API FastAPI con webhook de Telegram, Ollama como light LM, Caddy como reverse proxy con TLS automático vía DNS gratuito); frontend en Vercel; RDS PostgreSQL como almacén vectorial.

## Capabilities

### New Capabilities

- `knowledge-ingestion`: Pipeline que recopila contenido del portal FISI (noticias), PDFs del portal, FAQs curadas y portal central UNMSM; lo procesa (chunking, embeddings) y lo indexa en PostgreSQL (pgvector) con metadata de fuente y fecha.
- `prompt-injection-guard`: Defensa de entrada en dos capas (regex + light LM) que detecta y bloquea intentos de prompt injection, clasifica la consulta por tema/intención y decide si la consulta procede al pipeline RAG o se rechaza/deriva.
- `rag-answering`: Pipeline de respuesta que reescribe la consulta (light LM), recupera fragmentos relevantes de PostgreSQL (pgvector), genera la respuesta con DeepSeek 1017, la valida contra los fragmentos recuperados (anti-alucinación) y la entrega con citas a las fuentes.
- `usage-limits`: Límites de uso sin login: identificación anónima de usuarios (user ID de Telegram, session ID web), límites de frecuencia (5 consultas/minuto, 30/hora) y de longitud de consulta (500 caracteres).
- `telegram-ui`: Interfaz de chat vía bot de Telegram (webhook), con los mismos flujos de respuesta que la web.
- `web-ui`: Interfaz de chat web mobile-responsive publicada en Vercel, con diseño simple en azul (primario) y amarillo (acento).

### Modified Capabilities

(ninguna — proyecto nuevo, sin specs existentes)

## Impact

- **Nuevo código**: monorepo con backend Python/FastAPI, pipeline de ingesta y frontend React + TypeScript + Tailwind CSS; backend contenerizado con Docker.
- **Servicios externos**: Huawei Cloud ECS `ecs-innovabot` (4 vCPU / 8 GB RAM, EIP, región LA-Santiago, VPC `vpc-innova`), RDS PostgreSQL con pgvector (vector store), Huawei MaaS (DeepSeek 1017 como LLM principal), Ollama local en el ECS (light LM para guardián/clasificación/reescritura/validación), Vercel (hosting del frontend), Telegram Bot API (bot creado con BotFather) y DNS gratuito + Let's Encrypt vía Caddy (TLS del backend).
- **Fuentes de datos**: sistemas.unmsm.edu.pe (noticias y PDFs), unmsm.edu.pe, archivo de FAQs curadas mantenido por el equipo.
- **Sin impacto en sistemas existentes**: proyecto greenfield.
