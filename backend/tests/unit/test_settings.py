"""Tarea 1.4: settings tipado por variables de entorno."""

import pytest

from app.core.settings import get_settings

OBLIGATORIAS = [
    "MAAS_API_KEY",
    "MAAS_BASE_URL",
    "DATABASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "CORS_ORIGINS",
]


def test_falta_variable_obligatoria_mensaje_claro(monkeypatch, tmp_path):
    """Sin las variables obligatorias, la app falla con mensaje claro en español."""
    # tmp_path no tiene .env: el test no depende de un .env real en la máquina
    monkeypatch.chdir(tmp_path)
    for var in OBLIGATORIAS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(
        RuntimeError, match=r"Faltan variables de entorno obligatorias: .*DATABASE_URL"
    ):
        get_settings()


def test_faltan_todas_las_obligatorias(monkeypatch, tmp_path):
    """El mensaje lista todas las variables que faltan."""
    monkeypatch.chdir(tmp_path)
    for var in OBLIGATORIAS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        get_settings()
    for var in OBLIGATORIAS:
        assert var in str(excinfo.value)


def test_settings_carga_con_defaults(monkeypatch):
    """Con el env completo, los opcionales toman los valores por defecto del spec."""
    # Fijamos el env: el test no debe depender de un .env real de la máquina
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("RATE_LIMIT_PER_HOUR", "30")
    monkeypatch.setenv("MAX_QUERY_CHARS", "500")
    settings = get_settings()
    assert settings.rate_limit_per_minute == 5
    assert settings.rate_limit_per_hour == 30
    assert settings.max_query_chars == 500
    assert settings.main_llm_model == "deepseek-v4.1-flash"
    assert settings.light_llm_model == "qwen2.5:3b-instruct-q4_K_M"
    assert settings.embeddings_model == "intfloat/multilingual-e5-small"
    assert settings.origenes_cors == ["http://localhost:5173"]


def test_origenes_cors_varios():
    """CORS acepta varios orígenes separados por coma."""
    import os

    os.environ["CORS_ORIGINS"] = "https://a.vercel.app, https://b.vercel.app"
    try:
        assert get_settings().origenes_cors == [
            "https://a.vercel.app",
            "https://b.vercel.app",
        ]
    finally:
        os.environ["CORS_ORIGINS"] = "http://localhost:5173"
