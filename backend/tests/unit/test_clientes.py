"""Tarea 2.2: ClienteLLMPrincipal acotado (max_tokens, timeout).
Tarea 4.2: redacción de errores en clientes (LLM02).
Tarea 6.2: el cliente de embeddings usa la revisión fija del modelo (LLM03).
"""

import sys
import types

import pytest

from app.core.clientes import ClienteEmbeddings, ClienteLightLM
from app.core.settings import get_settings


def test_llm_principal_recibe_max_tokens_y_timeout(monkeypatch):
    """ClienteLLMPrincipal con LLM_MAX_TOKENS=77 y LLM_TIMEOUT_SECONDS=9
    pasa timeout al constructor OpenAI y max_tokens a create."""
    monkeypatch.setenv("LLM_MAX_TOKENS", "77")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "9")

    llamadas_constructor = []
    llamadas_create = []

    class FakeOpenAI:
        def __init__(self, **kwargs):
            llamadas_constructor.append(kwargs)

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            llamadas_create.append(kwargs)
            # Devolver una respuesta con la estructura esperada por el SDK
            class FakeChoice:
                class FakeMessage:
                    content = "respuesta"
                message = FakeMessage()

            class FakeResponse:
                choices = [FakeChoice()]

            return FakeResponse()

    monkeypatch.setattr("app.core.clientes.OpenAI", FakeOpenAI)

    from app.core.clientes import ClienteLLMPrincipal

    cliente = ClienteLLMPrincipal()
    # El constructor recibió timeout=9
    assert llamadas_constructor[0]["timeout"] == 9.0
    # Llamar a completar y verificar max_tokens=77
    cliente.completar("sistema", "usuario")
    assert llamadas_create[0]["max_tokens"] == 77


def test_completar_json_error_no_contiene_salida_cruda(monkeypatch):
    """completar_json con respuesta no-JSON → ValueError cuyo mensaje NO contiene
    la salida cruda del modelo (LLM02: redacción de errores)."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "esto no es JSON!!!"}

    class FakeClient:
        def __init__(self, timeout=None):
            pass

        def post(self, url, json=None):
            return FakeResponse()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr("app.core.clientes.httpx.Client", FakeClient)

    with pytest.raises(ValueError) as excinfo:
        ClienteLightLM().completar_json("sistema", "prompt")
    msg = str(excinfo.value)
    # El mensaje NO debe contener la salida cruda
    assert "esto no es JSON!!!" not in msg
    # Pero sí debe indicar que el JSON era inválido
    assert "JSON válido" in msg


def test_cliente_embeddings_usa_revision_fija(monkeypatch):
    """(harden-llm-security 6.2, LLM03) El modelo de embeddings se carga con la
    revisión configurada (EMBEDDINGS_REVISION), no con "latest"."""
    capturas = []

    class SentenceTransformerFake:
        def __init__(self, nombre, revision=None):
            capturas.append((nombre, revision))

    # El import es perezoso dentro de _cargar: se inyecta el módulo falso
    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=SentenceTransformerFake),
    )

    cliente = ClienteEmbeddings()
    cliente._cargar()
    settings = get_settings()
    assert capturas == [(settings.embeddings_model, settings.embeddings_revision)]
