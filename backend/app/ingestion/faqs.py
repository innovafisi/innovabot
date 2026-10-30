"""Carga de las FAQs curadas desde el Markdown del repo.

Formato del archivo (`data/faqs.md`): cada Q&A es un encabezado `## ¿Pregunta?`
seguido de la respuesta en Markdown hasta el siguiente `## `. Cada Q&A genera
exactamente un fragmento con `tipo=faq` (máxima prioridad en retrieval).
"""

from pathlib import Path

from app.core.modelos import Fragmento
from app.ingestion.chunking import hash_contenido

# Fuente curada por el equipo: no tiene URL web propia; el identificador
# estable permite que las citas de FAQ apunten a un origen reconocible.
URL_FAQS = "faq://preguntas-frecuentes-fisi"


def parsear_faqs(texto_md: str) -> list[tuple[str, str]]:
    """Parsea el Markdown en pares (pregunta, respuesta).

    Los encabezados de nivel 1 (`# `) se ignoran (título del archivo); cada
    `## Pregunta` abre un Q&A cuya respuesta llega hasta el siguiente encabezado.
    """
    pares: list[tuple[str, str]] = []
    pregunta_actual: str | None = None
    respuesta: list[str] = []
    for linea in texto_md.splitlines():
        if linea.startswith("## "):
            if pregunta_actual is not None:
                pares.append((pregunta_actual, "\n".join(respuesta).strip()))
            pregunta_actual = linea[3:].strip()
            respuesta = []
        elif pregunta_actual is not None:
            respuesta.append(linea)
    if pregunta_actual is not None:
        pares.append((pregunta_actual, "\n".join(respuesta).strip()))
    # Q&As sin respuesta no aportan conocimiento: se descartan
    return [(pregunta, respuesta) for pregunta, respuesta in pares if respuesta]


def cargar_faqs(ruta_md: str | Path) -> list[Fragmento]:
    """Carga las FAQs como fragmentos `tipo=faq` con id = hash del contenido."""
    texto = Path(ruta_md).read_text(encoding="utf-8")
    fragmentos: list[Fragmento] = []
    for pregunta, respuesta in parsear_faqs(texto):
        contenido = f"{pregunta}\n\n{respuesta}"
        fragmentos.append(
            Fragmento(
                id=hash_contenido(contenido),
                contenido=contenido,
                tipo="faq",
                url=URL_FAQS,
                titulo=pregunta,
                fecha=None,
            )
        )
    return fragmentos
