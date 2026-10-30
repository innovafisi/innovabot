"""Webhook de Telegram (spec telegram-ui).

Doble verificación de autenticidad: el token del bot va en la ruta (secreto)
y Telegram firma cada petición con el header X-Telegram-Bot-Api-Secret-Token.
Solo se atienden chats privados; /start y /help se responden sin entrar al
pipeline; el resto de mensajes pasa por el MISMO orquestador que la web,
con rate limit contra el user ID de Telegram.
"""

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.clientes import ClienteTelegram
from app.core.modelos import Respuesta
from app.core.settings import get_settings

logger = logging.getLogger("innovabot")

router = APIRouter()

MENSAJE_ERROR = (
    "Ocurrió un problema de mi lado al procesar tu consulta. "
    "Por favor intenta de nuevo más tarde."
)

BIENVENIDA = (
    "¡Hola! Soy InnovaBot, el asistente de consultas de la Facultad de "
    "Ingeniería de Sistemas e Informática (FISI) de la UNMSM.\n\n"
    "Pregúntame, por ejemplo:\n"
    "• ¿Cuándo es la matrícula del ciclo?\n"
    "• ¿Qué cursos tiene el plan de estudios?\n"
    "• ¿Cuáles son las últimas noticias de la facultad?"
)

AYUDA = (
    "Puedo atenderte en estos temas:\n"
    "• Admisión\n"
    "• Planes de estudio y cursos\n"
    "• Matrícula y trámites\n"
    "• Noticias y eventos de la FISI\n\n"
    "Comandos:\n"
    "/start — presentación del bot\n"
    "/help — esta ayuda"
)


class ChatTelegram(BaseModel):
    id: int
    type: str  # "private" | "group" | "supergroup" | "channel"


class UsuarioTelegram(BaseModel):
    id: int


class MensajeTelegram(BaseModel):
    message_id: int
    chat: ChatTelegram
    text: str | None = None
    # "from" es palabra reservada en Python: se mapea con alias
    from_user: UsuarioTelegram | None = Field(default=None, alias="from")


class UpdateTelegram(BaseModel):
    update_id: int
    message: MensajeTelegram | None = None


def formatear_respuesta(respuesta: Respuesta) -> str:
    """Texto plano para Telegram: la respuesta + las citas como lista."""
    if not respuesta.citas:
        return respuesta.reply
    fuentes = "\n".join(f"• {c.titulo}: {c.url}" for c in respuesta.citas)
    return f"{respuesta.reply}\n\nFuentes:\n{fuentes}"


def procesar_update(
    update: UpdateTelegram, pipeline, cliente: ClienteTelegram
) -> None:
    """Atiende un update: filtro de alcance, comandos y pipeline RAG."""
    mensaje = update.message
    if mensaje is None or not mensaje.text:
        return  # updates sin texto (canal, editados, medios) se descartan
    # Solo chats privados (spec telegram-ui): los grupos se descartan ANTES
    # del pipeline — sin respuesta, sin consumo de rate limit ni de LLMs.
    if mensaje.chat.type != "private":
        return
    texto = mensaje.text.strip()
    # Comandos: responden directamente, sin entrar al pipeline RAG
    if texto.startswith("/start"):
        cliente.enviar_mensaje(mensaje.chat.id, BIENVENIDA)
        return
    if texto.startswith("/help"):
        cliente.enviar_mensaje(mensaje.chat.id, AYUDA)
        return
    # Consulta normal: mismo orquestador que la web, identidad = user ID
    user_id = mensaje.from_user.id if mensaje.from_user else mensaje.chat.id
    try:
        respuesta = pipeline.procesar(texto, f"telegram:{user_id}", "telegram")
    except Exception:
        logger.exception("Fallo del pipeline ante un update de Telegram")
        cliente.enviar_mensaje(mensaje.chat.id, MENSAJE_ERROR)
        return
    cliente.enviar_mensaje(mensaje.chat.id, formatear_respuesta(respuesta))


@router.post("/telegram/webhook/{token}")
def webhook(
    token: str,
    update: UpdateTelegram,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Recibe updates de Telegram; 401/403 si la autenticación no coincide."""
    settings = get_settings()
    if token != settings.telegram_bot_token:
        raise HTTPException(status_code=403, detail="Token inválido")
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Secret token inválido")

    procesar_update(update, request.app.state.pipeline, request.app.state.telegram)
    # Telegram espera 200 rápido: los fallos ya se manejan dentro con mensaje amigable
    return {"ok": True}
