# InnovaBot — Chatbot RAG de la FISI (UNMSM)

Proyecto impulsado por el tercio estudiantil **Innova FISI**.

Chatbot con **RAG** (generación aumentada por recuperación) que responde
consultas sobre la Facultad de Ingeniería de Sistemas e Informática (FISI) de
la UNMSM **citando fuentes oficiales**, desde dos interfaces: un **bot de
Telegram** (chats privados) y una **web mobile-responsive**.

- Web: `https://innovabot.duckdns.org` (API del backend; frontend en Vercel)
- Backend: FastAPI + Ollama (light LM local) + RDS PostgreSQL con pgvector

## Características

- **Respuestas con citas**: cada respuesta indica las fuentes oficiales que la
  respaldan (portal FISI, portal UNMSM, PDFs, FAQs curadas).
- **Pipeline barato→caro por mensaje**: longitud → rate limit → regex anti
  prompt-injection → light LM (guardián + clasificación + reescritura) →
  retrieval semántico (pgvector, boost a FAQs) → LLM principal → validación
  anti-alucinación → respuesta.
- **Límites de uso sin login**: 5 consultas/min, 30/hora, 500 caracteres, con
  límite adicional por IP en la web.
- **Ingesta idempotente de 4 fuentes** (noticias, PDFs, FAQs, portal central),
  bajo cron semanal y disparo manual.
- **Hardening OWASP Top 10 para LLM**: aislamiento de contexto, guardián
  fail-closed, filtro anti-fuga, allowlist anti-SSRF, cadena de suministro
  fijada por hashes/digests — análisis en [`docs/owasp10llms-analisis.md`](docs/owasp10llms-analisis.md).

## Estructura del repo

```
backend/     # API FastAPI: pipeline RAG, guardián, ingesta, webhook Telegram
frontend/    # SPA React + TypeScript + Vite + Tailwind (arte de la cultura Lima)
docker/      # Dockerfiles y compose de desarrollo y producción (Caddy + TLS)
docs/        # bitácoras, guía de despliegue y análisis de seguridad
openspec/    # Fuente de verdad del comportamiento (specs) y cambios archivados
```

## Desarrollo

```bash
# Backend (Python 3.12+; los tests de integración se saltan sin entorno)
cd backend && pip install -e ".[dev]"
cp .env.example .env        # completar variables (nunca commitear .env)
pytest && ruff check .

# Frontend
cd frontend && npm install
npm run lint && npm run test -- --run && npm run build
```

La operación completa del backend (ingesta, contrato del pipeline, variables)
está en [`backend/README.md`](backend/README.md).

## Despliegue

Producción corre en Huawei Cloud (ECS + RDS con pgvector) con Docker Compose:
solo Caddy publica 80/443 con TLS automático. El paso a paso, la verificación
end-to-end y los problemas comunes están en
[`docs/guia-deploy.md`](docs/guia-deploy.md).

## Documentación

- [`openspec/specs/`](openspec/specs/) — comportamiento del sistema por
  capability (fuente de verdad).
- [`docs/bitacora.md`](docs/bitacora.md) / [`docs/bitacora-dev.md`](docs/bitacora-dev.md) —
  memoria del proyecto: decisiones, infraestructura e incidentes.
- [`docs/owasp10llms-analisis.md`](docs/owasp10llms-analisis.md) — análisis de
  seguridad LLM y mitigaciones aplicadas.
- [`AGENTS.md`](AGENTS.md) — reglas de trabajo para contribuir (OpenSpec, KISS,
  secretos solo por variables de entorno).

## Seguridad

El repo es **público**: nunca commitees credenciales (todo va por variables de
entorno; `gitleaks` corre como pre-commit hook). Si encuentras una
vulnerabilidad, repórtala privadamente al equipo de Innova FISI antes de
abrir un issue público.
