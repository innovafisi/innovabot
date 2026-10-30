"""Logs estructurados del proyecto.

Dos registros, sin contenido de consultas ni datos personales:
- `innovabot.consultas`: una línea JSON por consulta RECIBIDA con
  {interfaz, categoria, estado, latencia_ms, timestamp} (spec rag-answering).
- `innovabot.guardian`: un registro por intento bloqueado con
  {motivo, timestamp, interfaz} (spec prompt-injection-guard).
"""

import json
import logging
import time

logger_consultas = logging.getLogger("innovabot.consultas")
logger_guardian = logging.getLogger("innovabot.guardian")


def _registrar(logger: logging.Logger, evento: str, **campos) -> None:
    registro = {"evento": evento, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    registro.update(campos)
    logger.info(json.dumps(registro, ensure_ascii=False))


def registrar_consulta(
    interfaz: str, estado: str, latencia_ms: int, categoria: str | None = None
) -> None:
    """Log por consulta recibida; categoria solo si la consulta fue clasificada."""
    _registrar(
        logger_consultas,
        "consulta",
        interfaz=interfaz,
        categoria=categoria,
        estado=estado,
        latencia_ms=latencia_ms,
    )


def registrar_bloqueo(motivo: str, interfaz: str) -> None:
    """Log de auditoría por intento bloqueado (regex o light LM)."""
    _registrar(logger_guardian, "bloqueo", motivo=motivo, interfaz=interfaz)
