#!/usr/bin/env bash
# Descarga el light LM en el contenedor de Ollama del compose de desarrollo
# y verifica que `GET /api/tags` lo lista (tarea 1.5 de tasks.md).
# Uso: bash scripts/descargar_modelo.sh   (desde la raíz del repo)

set -euo pipefail

MODEL="${LIGHT_LLM_MODEL:-qwen2.5:3b-instruct-q4_K_M}"

echo "==> Descargando modelo ${MODEL} en el contenedor de Ollama…"
docker compose -f docker/docker-compose.yml up -d ollama
docker compose -f docker/docker-compose.yml exec ollama ollama pull "$MODEL"

echo "==> Verificación: GET /api/tags debe listar ${MODEL}"
curl -s http://127.0.0.1:11434/api/tags | grep -q "$MODEL" \
  && echo "OK: el modelo aparece en /api/tags" \
  || { echo "ERROR: el modelo no aparece en /api/tags"; exit 1; }
