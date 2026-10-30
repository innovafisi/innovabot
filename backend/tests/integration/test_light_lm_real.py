"""Prueba de integración contra Ollama REAL (tarea 3.2).

Requiere Ollama corriendo con el light LM descargado
(`bash scripts/descargar_modelo.sh`). Sin Ollama en la máquina (p. ej. sin
Docker en desarrollo) se salta: los unit tests mockean el light LM.
"""

import httpx
import pytest

from app.core.clientes import ClienteLightLM
from app.core.settings import get_settings
from app.guard.light_lm_guard import evaluar_consulta


def _ollama_con_modelo() -> bool:
    settings = get_settings()
    try:
        respuesta = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        if respuesta.status_code != 200:
            return False
        nombres = " ".join(m.get("name", "") for m in respuesta.json().get("models", []))
        return settings.light_llm_model in nombres
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_con_modelo(), reason="Ollama no disponible o sin el light LM (integración)"
)


def test_guard_con_ollama_real_devuelve_json_parseable():
    """Contra Ollama real, la llamada combinada devuelve JSON con las tres claves."""
    resultado = evaluar_consulta(
        "¿hasta cuándo puedo matricularme en la FISI?", ClienteLightLM()
    )
    # El JSON se parsea correctamente y las claves tienen tipos esperados
    assert isinstance(resultado.safe, bool)
    assert isinstance(resultado.categoria, str) and resultado.categoria
    assert isinstance(resultado.consulta_reescrita, str) and resultado.consulta_reescrita
