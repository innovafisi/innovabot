"""Fixtures globales: variables de entorno dummy para todos los tests.

Los tests unitarios mockean los clientes externos; estas variables solo
permiten instanciar settings sin tocar credenciales reales.
"""

import os

import pytest

from app.core.settings import get_settings

DUMMY_ENV = {
    "MAAS_API_KEY": "test-key",
    "MAAS_BASE_URL": "http://maas.test/v1",
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "TELEGRAM_BOT_TOKEN": "123456:test-token",
    "TELEGRAM_WEBHOOK_SECRET": "secreto-test",
    "CORS_ORIGINS": "http://localhost:5173",
    "RATE_LIMIT_PER_MINUTE": "5",
    "RATE_LIMIT_PER_HOUR": "30",
    "MAX_QUERY_CHARS": "500",
}


def _fijar_env_dummy() -> None:
    # setdefault: los tests que necesitan sobreescribir pueden hacerlo con monkeypatch
    for clave, valor in DUMMY_ENV.items():
        os.environ.setdefault(clave, valor)


_fijar_env_dummy()


@pytest.fixture(autouse=True)
def _settings_frescas():
    """Cada test instancia settings con el env vigente (sin caché cruzada)."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
