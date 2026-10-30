"""Filtro regex de prompt injection (spec prompt-injection-guard, capa 1).

Corre SIEMPRE antes que cualquier modelo (coste cero). Los patrones están
anclaados a instrucciones completas (override, revelación del system prompt,
jailbreak), nunca a palabras sueltas: una consulta legítima que mencione una
palabra sospechante aislada no se bloquea (escenario del spec).
"""

import re

# (motivo, patrón): el motivo alimenta el registro de auditoría (tarea 3.4).
_PATRONES: list[tuple[str, re.Pattern[str]]] = [
    # Override de instrucciones previas (ES / EN)
    (
        "override_instrucciones",
        re.compile(
            r"(ignora|olvida|desconecta|haz caso omiso de|no sigas|desobedece"
            r"|deja de seguir)[^\n]{0,40}(instrucciones|indicaciones|reglas|prompts?)",
            re.IGNORECASE,
        ),
    ),
    (
        "override_instrucciones",
        re.compile(
            r"(ignore|forget|disregard|do not follow|stop following)"
            r"[^\n]{0,40}(instructions?|rules?|prompts?)",
            re.IGNORECASE,
        ),
    ),
    # Revelar el system prompt o las instrucciones internas
    (
        "revelar_system_prompt",
        re.compile(
            r"(revela|mu[eé]stra(?:me)?|imprime|repite|dame|d[ií]me|cu[áa]l es)"
            r"[^\n]{0,40}"
            r"(system ?prompt|prompt (del|tu) sistema|prompt inicial"
            r"|instrucciones (internas|del sistema|secretas)|tus instrucciones)",
            re.IGNORECASE,
        ),
    ),
    (
        "revelar_system_prompt",
        re.compile(
            r"(reveal|show|print|repeat|give me|what is)[^\n]{0,40}system ?prompt",
            re.IGNORECASE,
        ),
    ),
    # Jailbreak: rol sin restricciones o modos prohibidos
    (
        "jailbreak",
        re.compile(
            r"(act[úu]a|comporta(?:rte|te)|convi[eé]rtete|hazte)"
            r"[^\n]{0,40}(como|en)[^\n]{0,40}"
            r"(sin restricciones|sin filtros|sin censura|sin reglas|jailbroken|dan\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"act as[^\n]{0,40}(unrestricted|unfiltered|jailbroken|dan\b|without any rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"(entra|activa)[^\n]{0,20}(modo|mode)[^\n]{0,20}"
            r"(dan|jailbreak|developer|desarrollador)",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak",
        re.compile(
            r"(you are now|desde ahora eres|a partir de ahora eres)[^\n]{0,40}"
            r"(sin restricciones|without restrictions|any restrictions|libre de reglas|dan\b)",
            re.IGNORECASE,
        ),
    ),
]


def patron_inyeccion(consulta: str) -> str | None:
    """Motivo del primer patrón de inyección que coincide, o None si está limpia."""
    for motivo, patron in _PATRONES:
        if patron.search(consulta):
            return motivo
    return None
