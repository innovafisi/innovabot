"""Mensajes estándar del bot en español.

Única fuente de los textos que reciben los usuarios (specs
prompt-injection-guard, rag-answering y usage-limits): derivación temprana
sin invocar retrieval ni LLM principal.
"""

PORTAL_OFICIAL = "https://sistemas.unmsm.edu.pe"

BLOQUEADA = (
    "Lo siento, no puedo atender ese tipo de consulta. InnovaBot responde "
    "únicamente preguntas sobre la FISI y la UNMSM con base en fuentes oficiales."
)

FUERA_ALCANCE = (
    "Esa consulta está fuera de los temas que puedo atender. Puedo ayudarte con: "
    "admisión, planes de estudio, matrícula y trámites, y noticias de la FISI (UNMSM)."
)

SIN_RESULTADOS = (
    "No encontré información verificada sobre esa consulta. Te sugiero revisar el "
    f"portal oficial de la FISI: {PORTAL_OFICIAL}"
)

NO_VERIFICADA = (
    "No pude verificar esa información con las fuentes disponibles, así que "
    "prefiero no responderla. Prueba reformulando la consulta o revisa el portal "
    f"oficial: {PORTAL_OFICIAL}"
)

# Fallo del propio servicio (timeout o error del LLM principal): mensaje
# amigable sin detalles técnicos (harden-llm-security, LLM02/LLM10).
ERROR_SERVICIO = (
    "Ocurrió un problema de mi lado al procesar tu consulta. "
    "Por favor intenta de nuevo más tarde."
)

SIN_SESION = "No pude identificar tu sesión. Recarga la página e intenta de nuevo."


def consulta_larga(max_chars: int) -> str:
    return (
        f"Tu consulta supera el límite de {max_chars} caracteres. "
        "Por favor acórtala para que pueda atenderla."
    )


def limite_excedido(reintento_segundos: int) -> str:
    minutos = max(1, round(reintento_segundos / 60))
    plural = "s" if minutos != 1 else ""
    return (
        "Has alcanzado el límite de consultas por ahora. Espera unos "
        f"{minutos} minuto{plural} antes de intentar de nuevo."
    )
