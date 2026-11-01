# Proposal — Acotar el contexto de validación para reducir latencia

## Why

En el ECS (CPU-only), el pipeline cumple funcionalmente pero tarda ~30–40 s por
consulta. El desglose medido muestra que el **light LM** es el cuello, y dentro
de él la **validación anti-alucinación** (~19 s): su prompt incluye el contenido
completo de los 5 fragmentos recuperados (~1000 tokens de prompt-eval), y cuando
la validación falla el orquestador regenera y **vuelve a validar** (≈ +21 s).
El objetivo de diseño es <10 s por respuesta.

## What Changes

- La validación SHALL usar un **contexto acotado**: como máximo unos pocos
  fragmentos (los más relevantes, ya ordenados por el retrieval) y cada uno
  truncado a un máximo de caracteres. Así baja el prompt-eval del light LM sin
  perder las fuentes principales de respaldo.
- Sin cambios en el contrato de respuesta ni en los textos al usuario.

## Capabilities

### New Capabilities

(ninguna)

### Modified Capabilities

- `rag-answering`: la validación anti-alucinación se hace sobre un contexto
  acotado (número de fragmentos y longitud por fragmento), para acotar latencia.

## Impact

- **Código**: `backend/app/rag/validacion.py` (recorte del prompt) y un test
  unitario nuevo.
- **Sin cambios de UX**; el contrato `ok|bloqueada|sin_resultados|limitada` no
  cambia.
- **Despliegue**: rebuild de la imagen `app` y `up -d` en el ECS; medir latencia.
- **Nota de calidad**: al truncar evidencia, una respuesta que dependiera de
  texto más allá del corte podría marcarse como no respaldada (y regenerar). Se
  mitiga usando los fragmentos más relevantes y un límite holgado.
