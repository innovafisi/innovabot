"""Filtro de salida contra fuga de instrucciones del sistema (LLM07).

Un canario — cadena aleatoria única por proceso — viaja al final de los
system prompts de generación y validación. Si el modelo filtra sus
instrucciones de forma verbatim, la respuesta contiene el canario y se
bloquea antes de llegar al usuario: no dependemos de la obediencia del
modelo, sino de una detección determinista en la salida.
"""

import secrets

# Canario por proceso: aleatorio en cada arranque, improbable en una
# respuesta legítima. Los system prompts lo incluyen (ver rag/generacion.py
# y rag/validacion.py); el orquestador lo busca en la respuesta generada.
CANARIO = f"INNOVABOT-CANARIO-{secrets.token_hex(12)}"


def contiene_fuga(texto: str) -> bool:
    """True si el texto delata una fuga verbatim de instrucciones del sistema."""
    return CANARIO in texto
