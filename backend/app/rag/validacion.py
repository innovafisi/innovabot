"""Validación anti-alucinación con el light LM (spec rag-answering).

Segunda llamada al light LM (la primera es la combinada del guardián):
verifica que las afirmaciones de la respuesta estén respaldadas por los
fragmentos recuperados, antes de entregarla al usuario.
"""

from app.core.clientes import ClienteLightLM
from app.core.modelos import Fragmento

SISTEMA_VALIDACION = """\
Eres un validador estricto y objetivo. Se te da una respuesta generada y los \
fragmentos que la respaldan. Verificas que CADA afirmación de la respuesta \
esté respaldada por el contenido de los fragmentos.
Respondes SOLO con un objeto JSON: {"respaldada": true} si toda la respuesta \
se desprende de los fragmentos, o {"respaldada": false, "problemas": "breve \
descripción de las afirmaciones sin respaldo"} en caso contrario."""


def armar_prompt_validacion(respuesta: str, fragmentos: list[Fragmento]) -> str:
    contexto = "\n\n".join(f.contenido for f in fragmentos)
    return f"Fragmentos:\n{contexto}\n\nRespuesta generada:\n{respuesta}"


def validar(
    respuesta: str, fragmentos: list[Fragmento], cliente_light: ClienteLightLM
) -> bool:
    """True si la respuesta está respaldada por los fragmentos."""
    salida = cliente_light.completar_json(
        SISTEMA_VALIDACION, armar_prompt_validacion(respuesta, fragmentos)
    )
    return bool(salida.get("respaldada", False))
