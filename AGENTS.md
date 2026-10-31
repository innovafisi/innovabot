# AGENTS.md

Guía para agentes de código (y humanos) que trabajan en este repo.

## Qué es este repo

**InnovaBot**: chatbot RAG para consultas sobre la Facultad de Ingeniería de Sistemas e Informática (FISI) de la UNMSM. Dos interfaces — bot de Telegram y web mobile-responsive — sobre un único pipeline de respuesta con citas a fuentes oficiales.

Estado: **planificación completa, sin código todavía**. Todo el plan vive en OpenSpec (ver abajo); la implementación arranca con el cambio `add-fisi-rag-chatbot`.

## Flujo de trabajo: OpenSpec (obligatorio)

Este repo usa OpenSpec con schema `spec-driven`. La fuente de verdad del comportamiento está en los specs, no en este archivo.

- **Antes de implementar algo nuevo**: usa los workflows `opsx` (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`). No edites código de features sin un cambio OpenSpec que lo respalde.
- **Cambio activo**: `openspec/changes/add-fisi-rag-chatbot/` — `proposal.md` (qué y por qué), `specs/` (comportamiento por capability), `design.md` (cómo: TODAS las decisiones técnicas), `tasks.md` (41 tareas con verificación cada una, en 7 grupos).
- **Para aplicar**: sigue `tasks.md` en orden, marcando los checkboxes al completar. Cada tarea dice cómo verificarse — no la des por hecha sin esa verificación.
- **Decisiones de producto ya tomadas** (no las reabras): están en `design.md` con sus alternativas descartadas. Si el usuario pide cambiar una, actualiza specs/design/tasks para mantenerlos coherentes.
- **Idioma**: todos los artifacts OpenSpec, READMEs, mensajes de usuario y respuestas del bot van en **español**.

## Arquitectura (resumen)

Los detalles completos están en `design.md` del cambio activo. Lo esencial:

- **Backend**: monolito modular en Python/FastAPI (`backend/app/` con `core/`, `ingestion/`, `guard/`, `rag/`, `interfaces/`). Tres entrypoints: API web + webhook Telegram (`uvicorn`) e ingesta batch (`python -m app.ingest`, cron semanal + disparo manual).
- **Pipeline por mensaje** (del chequeo más barato al más caro): longitud ≤500 chars → rate limit (5/min, 30/hora, en memoria) → regex anti prompt-injection → light LM (Ollama local, `qwen2.5:3b-instruct-q4_K_M`: guard + clasificación + reescritura en UNA llamada JSON) → retrieval pgvector → LLM principal `deepseek-v4.1-flash` (MaaS, endpoint compatible con OpenAI) → validación anti-alucinación → respuesta con citas.
- **Vector store**: RDS PostgreSQL `rds-innovabot` (PostgreSQL 18, base `rag_fisi`, pgvector instalado), en la VPC, puerto 5432 nunca expuesto a internet.
- **Embeddings**: sentence-transformers `multilingual-e5-small`, local en el backend.
- **Frontend**: React + TypeScript + Vite + ESLint + Tailwind, publicado en Vercel. CORS en FastAPI solo para el origen de Vercel. El backend NO sirve los estáticos.
- **Despliegue**: Huawei Cloud ECS `ecs-innovabot` (LA-Santiago, 4 vCPU / 8 GB, EIP) con Docker Compose: `app` y `ollama` internos, **solo Caddy publica 80/443** con Let's Encrypt contra un DNS gratuito. Deploy manual por SSH.
- **Telegram**: solo chats privados; updates de grupos se descartan antes del pipeline.
- **Diseño web**: azul `#003b71` primario, amarillo `#ffc72c` acento, terracota `#b3502d` secundario; rasgos del arte de la cultura Lima (banda de triángulos entrelazados, huaca escalonada, greca). Modo claro/oscuro, claro por defecto. Prototipo aprobado: `index-lima.html` en la raíz.

## Estructura del repo

```
backend/     # Python/FastAPI (por crear — grupo 1 de tasks.md)
frontend/    # React + TS + Vite + Tailwind (por crear)
docker/      # Dockerfiles y docker-compose (por crear)
docs/        # bitacora.md (planificación/infra), bitacora-dev.md (implementación), guia-deploy.md (despliegue ECS+Vercel)
openspec/    # Specs y cambios OpenSpec — NO editar casualmente
index-lima.html  # Prototipo de diseño aprobado (referencia para la SPA)
index.html       # Prototipo previo sin arte Lima (referencia histórica)
```

## Convenciones de código

- **KISS (regla transversal)**: la solución más simple que cumpla los specs gana. Sin abstracciones especulativas, servicios extra ni optimización prematura — cada pieza de complejidad debe justificarse contra un requisito o un riesgo documentado en `design.md`.
- **Backend**: Python 3.12+, `pyproject.toml`, pytest para tests, ruff para lint. Los clientes externos (MaaS, Ollama, RDS, Telegram) se abstraen tras interfaces en `core/` — nunca llames APIs externas directamente desde `guard/`, `rag/` o `interfaces/`.
- **Frontend**: TypeScript estricto, ESLint sin errores, Tailwind con tokens de color en `theme.extend.colors` (no colores hardcodeados).
- **Tests**: cada grupo de tareas aterriza sus propios tests; los mocks de LLM son la norma para unit tests — las pruebas contra Ollama/RDS reales son de integración y están marcadas como tales en `tasks.md`.
- **Secrets**: solo por variables de entorno (módulo de settings tipado); nunca en código ni commits. **Gitleaks** corre como pre-commit hook (y paso de CI si existe): si marca un hallazgo, rota la credencial afectada antes de seguir — el repo es público.

## Comandos (una vez creado el scaffolding)

```bash
# Backend
cd backend && pytest
cd backend && ruff check .

# Frontend
cd frontend && npm run lint
cd frontend && npm run build

# Docker local
docker compose -f docker/docker-compose.yml up

# Escaneo de secretos
gitleaks detect --source . -v

# OpenSpec
openspec status --change add-fisi-rag-chatbot
openspec validate add-fisi-rag-chatbot
```
