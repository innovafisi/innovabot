"""Webhook de Telegram (spec telegram-ui).

Autenticación SOLO por header X-Telegram-Bot-Api-Secret-Token (LLM02:
el token del bot ya no viaja en la URL ni llega a los access logs).
Solo se atienden chats privados; /start y /help se responden sin entrar al
pipeline; el resto de mensajes pasa por el MISMO orquestador que la web,
con rate limit contra el user ID de Telegram.
"""

import logging
import time
from collections.abc import Callable

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


class RegistroUpdates:
    """Anti-replay de update_ids con TTL (LLM10): evita reprocesar updates
    que Telegram reenvía tras un timeout del webhook. Semántica at-least-once
    con deduplicación en éxito."""

    def __init__(
        self, ttl: float = 3600.0, reloj: Callable[[], float] = time.monotonic
    ) -> None:
        self.ttl = ttl
        self._reloj = reloj
        self._vistos: dict[int, float] = {}  # update_id -> marca de tiempo

    def ya_visto(self, update_id: int) -> bool:
        """True si el update_id ya fue procesado; lo marca como visto si no."""
        ahora = self._reloj()
        # Purgar expirados
        self._vistos = {
            uid: marca for uid, marca in self._vistos.items() if ahora - marca < self.ttl
        }
        if update_id in self._vistos:
            return True
        self._vistos[update_id] = ahora
        return False


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
    except Exception as exc:
        # LLM02: solo el tipo de la excepción, nunca el mensaje (puede
        # contener DSN o credenciales).
        logger.error(
            "Fallo del pipeline ante un update de Telegram (%s)", type(exc).__name__
        )
        cliente.enviar_mensaje(mensaje.chat.id, MENSAJE_ERROR)
        return
    cliente.enviar_mensaje(mensaje.chat.id, formatear_respuesta(respuesta))


@router.post("/telegram/webhook")
def webhook(
    update: UpdateTelegram,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Recibe updates de Telegram; 401 si el secret token no coincide."""
    settings = get_settings()
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="Secret token inválido")

    # Anti-replay (LLM10): si el update ya fue procesado, responder ok sin reprocesar
    registro: RegistroUpdates = request.app.state.updates_telegram
    if registro.ya_visto(update.update_id):
        return {"ok": True}

    try:
        procesar_update(update, request.app.state.pipeline, request.app.state.telegram)
    except Exception:
        # Si procesar_update lanza (p. ej. fallo de red enviando), el update
        # no queda marcado como visto, el webhook devuelve 500 y Telegram
        # reintenta (semántica at-least-once con deduplicación en éxito).
        logger.error("Error inesperado procesando update de Telegram")
        raise HTTPException(status_code=500, detail="Error interno") from None
    return {"ok": True}
