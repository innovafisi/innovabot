"""API web: POST /api/chat (spec web-ui, tarea 5.1).

Contrato: entrada {"query": string} + header X-Session-ID; salida
{"reply", "citas": [{"titulo", "url"}], "estado"} con HTTP 429 cuando el
estado es "limitada". CORS restringido al origen de Vercel por variable de
entorno (CORS_ORIGINS).
"""

from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.limites import LimiteExcedido
from app.core.modelos import Respuesta
from app.guard import mensajes

router = APIRouter()


class CuerpoChat(BaseModel):
    """Entrada del endpoint: la consulta del usuario."""

    query: str = Field(min_length=1, description="Consulta del usuario (≤500 caracteres)")


def _cuerpo_respuesta(respuesta: Respuesta) -> dict[str, Any]:
    return {
        "reply": respuesta.reply,
        "citas": [{"titulo": c.titulo, "url": c.url} for c in respuesta.citas],
        "estado": respuesta.estado,
    }


def _respuesta_http(respuesta: Respuesta) -> JSONResponse:
    """200 en general; 429 cuando el límite de uso está excedido (estado limitada)."""
    codigo = 429 if respuesta.estado == "limitada" else 200
    return JSONResponse(status_code=codigo, content=_cuerpo_respuesta(respuesta))


def _ip_cliente(request: Request) -> str:
    """IP del cliente: X-Forwarded-For (primera IP) o request.client.host.

    En producción Caddy es el único proxy, se confía en su XFF.
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "desconocida"


@router.post("/api/chat")
def chat(
    cuerpo: CuerpoChat,
    request: Request,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> JSONResponse:
    """Procesa una consulta web a través del mismo orquestador que Telegram."""
    pipeline = request.app.state.pipeline
    if not x_session_id:
        # Sin session ID no hay identidad para el rate limit: se rechaza como limitada
        return _respuesta_http(Respuesta(reply=mensajes.SIN_SESION, estado="limitada"))
    # Límite por IP (LLM10): rotar el session ID desde una misma IP no da cupo infinito.
    # Se aplica ANTES de llamar al pipeline para no consumir recursos.
    ip = _ip_cliente(request)
    try:
        request.app.state.limites_ip.verificar_ip(ip)
    except LimiteExcedido as exc:
        return _respuesta_http(
            Respuesta(reply=mensajes.limite_excedido(exc.reintento_segundos), estado="limitada")
        )
    resultado = pipeline.procesar(
        cuerpo.query, identidad=f"web:{x_session_id}", interfaz="web"
    )
    return _respuesta_http(resultado)
