"""Cambio reduce-validation-latency: la validación usa un contexto acotado.

El prompt del validador se limita a los fragmentos más relevantes y trunca
cada uno, para acotar el prompt-eval del light LM en despliegues CPU-only.
"""

from app.rag.validacion import (
    MAX_CARACTERES_POR_FRAGMENTO,
    MAX_FRAGMENTOS_VALIDACION,
    SISTEMA_VALIDACION,
    armar_prompt_validacion,
    validar,
)
from tests.unit.fakes import FakeLightLM, fragmento_prueba


def _fragmento_largo(id_: str, contenido: str) -> object:
    return fragmento_prueba(id_=id_, contenido=contenido, url=f"https://x/{id_}")


def test_prompt_limita_cantidad_de_fragmentos():
    """Con más fragmentos que el máximo, el prompt solo incluye los primeros."""
    fragmentos = [
        _fragmento_largo(f"f{i}", f"Contenido del fragmento {i}." * 5)
        for i in range(5)
    ]
    prompt = armar_prompt_validacion("respuesta", fragmentos)
    # Solo los MAX_FRAGMENTOS_VALIDACION primeros, numerados 1..N
    assert prompt.count("<<<FRAGMENTO") == MAX_FRAGMENTOS_VALIDACION
    assert "<<<FRAGMENTO 1 " in prompt
    assert f"<<<FRAGMENTO {MAX_FRAGMENTOS_VALIDACION} " in prompt
    assert f"<<<FRAGMENTO {MAX_FRAGMENTOS_VALIDACION + 1} " not in prompt
    # Los incluidos son los más relevantes (los primeros de la lista)
    assert "Contenido del fragmento 0." in prompt
    assert "Contenido del fragmento 3." not in prompt


def test_prompt_trunca_fragmentos_largos():
    """Cada fragmento aporta como máximo MAX_CARACTERES_POR_FRAGMENTO + ellipsis."""
    largo = "x" * (MAX_CARACTERES_POR_FRAGMENTO + 500)
    fragmentos = [_fragmento_largo("largo", largo)]
    prompt = armar_prompt_validacion("respuesta", fragmentos)
    # El contenido viaja truncado y marcado con …
    assert ("x" * MAX_CARACTERES_POR_FRAGMENTO + "…") in prompt
    assert "x" * (MAX_CARACTERES_POR_FRAGMENTO + 1) not in prompt


def test_recorte_no_muta_los_fragmentos_originales():
    """El recorte trabaja sobre copias: los Fragmento originales quedan intactos."""
    largo = "y" * (MAX_CARACTERES_POR_FRAGMENTO + 100)
    fragmento = _fragmento_largo("original", largo)
    armar_prompt_validacion("respuesta", [fragmento])
    assert len(fragmento.contenido) == MAX_CARACTERES_POR_FRAGMENTO + 100
    assert "…" not in fragmento.contenido


def test_fragmentos_cortos_pasan_igual():
    """Fragmentos por debajo del límite viajan completos, sin ellipsis."""
    fragmentos = [_fragmento_largo("corto", "Matrícula del 10 al 20 de marzo.")]
    prompt = armar_prompt_validacion("respuesta", fragmentos)
    assert "Matrícula del 10 al 20 de marzo." in prompt
    assert "…" not in prompt.split("Respuesta generada:")[0]


def test_validar_mantiene_el_contrato_con_el_light_lm():
    """Regression: validar() sigue evaluando {respaldada} sin cambiar de contrato."""
    fragmentos = [_fragmento_largo("f", "La matrícula es en marzo.")]
    cliente_ok = FakeLightLM({"respaldada": True})
    assert validar("La matrícula es en marzo.", fragmentos, cliente_ok) is True
    cliente_no = FakeLightLM({"respaldada": False, "problemas": "inventado"})
    assert validar("La matrícula es en agosto.", fragmentos, cliente_no) is False
    # El system prompt conserva el centinela anti-fuga y la instrucción de evidencia
    sistema, _prompt = cliente_ok.llamadas[0]
    assert sistema == SISTEMA_VALIDACION
    assert "evidencia a verificar" in sistema
