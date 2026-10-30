"""App FastAPI de InnovaBot.

Un solo servicio con los endpoints de la API web (/api/chat) y del webhook
de Telegram (/telegram/webhook/{token}). CORS únicamente para el origen del
frontend en Vercel (CORS_ORIGINS); el backend NO sirve estáticos.
"""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.clientes import ClienteTelegram
from app.core.settings import get_settings
from app.interfaces.api import router as router_api
from app.interfaces.telegram import router as router_telegram


def crear_app(pipeline: Any = None, cliente_telegram: Any = None) -> FastAPI:
    """Crea la app; `pipeline` y `cliente_telegram` inyectables para tests."""
    settings = get_settings()
    app = FastAPI(title="InnovaBot API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origenes_cors,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["X-Session-ID", "Content-Type"],
    )
    if pipeline is None:
        from app.rag.orquestador import construir_orquestador

        pipeline = construir_orquestador()
    if cliente_telegram is None:
        cliente_telegram = ClienteTelegram()
    app.state.pipeline = pipeline
    app.state.telegram = cliente_telegram
    app.include_router(router_api)
    app.include_router(router_telegram)
    return app


app = crear_app()
