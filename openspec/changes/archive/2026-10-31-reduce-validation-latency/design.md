# Design — Acotar el contexto de validación

## Context

`backend/app/rag/validacion.py` construye el prompt del validador concatenando
el contenido completo de todos los fragmentos recuperados. En CPU (sin GPU) el
prompt-eval de ~1000 tokens cuesta ~19 s por validación; si falla, hay
regeneración + segunda validación. Medido en el ECS con `qwen2.5:3b` y
`c7n.xlarge.2` (AVX2/AVX-512): guard ~4 s, validación ~19 s, MaaS ~2 s.

## Goals / Non-Goals

**Goals:** bajar la latencia de la validación de forma simple y reversible,
manteniendo la detección de alucinaciones sobre las fuentes principales.

**Non-Goals:** cambiar el modelo del light LM, el retrieval, ni el contrato de
respuesta. No se toca la generación (el LLM principal es rápido).

## Decisions

- **Decisión:** en `armar_prompt_validacion`, tomar los primeros
  `MAX_FRAGMENTOS_VALIDACION = 3` fragmentos (ya vienen ordenados por relevancia
  y boost de FAQ) y truncar cada uno a
  `MAX_CARACTERES_POR_FRAGMENTO = 600` caracteres (con `…` si se corta).
  Constantes en el módulo (KISS, sin variable de entorno nueva).
- **Por qué:** reduce el prompt-eval de ~1000 a ~375 tokens (≈ -60%), lo que
  recorta la validación y, sobre todo, el coste doble cuando hay regeneración.
  Los 3 fragmentos top contienen casi siempre la evidencia usada.
- **Alternativas descartadas:** quitar la validación (pierde la mitigación de
  alucinaciones); modelo más pequeño (otro cambio); top-k global menor (afecta
  también a la generación y a las citas).
- **Riesgo/trade-off:** si la respuesta se apoya en un fragmento fuera del
  top-3 o más allá del carácter 600, el validador podría marcarla sin respaldo y
  provocar una regeneración. Se acepta: el retrieval prioriza lo relevante y el
  límite es holgado; si apareciera en pruebas, se ajustan las constantes.

## Migration Plan

Rebuild de la imagen `app` y `up -d app` en el ECS; medir latencia de `/api/chat`
en caliente. Rollback: revertir las constantes (o volver a la imagen anterior).
