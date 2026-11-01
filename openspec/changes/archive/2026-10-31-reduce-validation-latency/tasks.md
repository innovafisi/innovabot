# Tasks

## 1. Acotar el contexto de validación

- [x] 1.1 En `backend/app/rag/validacion.py`, limitar la validación a los `MAX_FRAGMENTOS_VALIDACION=3` primeros fragmentos y truncar cada uno a `MAX_CARACTERES_POR_FRAGMENTO=600` caracteres antes de armar el prompt. Verificar con un test unitario que el prompt no supera esos límites y que trunca con `…`.
- [x] 1.2 Regression: la suite unitaria del orquestador y de generación sigue en verde (el validador con fake no cambia de contrato).

## 2. Despliegue y medición

- [x] 2.1 Rebuild de la imagen `app` en el ECS y `up -d app`. Verificar `/api/chat` end-to-end (`estado: ok`) y **medir latencia en caliente**; documentar la mejora frente a la línea base (~30–40 s). **Verificado (2026-10-31, ECS)**: latencia en caliente 10.7–10.9 s (antes 32–40 s, −70%); primera consulta ~31 s (carga del modelo e5 en RAM, ahora persistido en volumen `hf-cache`). En el límite del objetivo <10 s.

## Workflow follow-up

- Archivar tras revisión; documentar el resultado de latencia en la bitácora.
