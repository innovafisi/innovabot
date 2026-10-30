"""Normalización de contenido, hash de deduplicación y chunking por secciones.

El id de cada fragmento es el hash SHA-256 de su contenido normalizado
(deduplicación por upsert, ver `core/modelos.py`). El chunking preserva las
secciones del documento: cada sección genera al menos un fragmento, y las
secciones muy largas se dividen en ventanas con solapamiento.
"""

import hashlib
import re

from app.core.modelos import Fragmento

# ~200 tokens por ventana (~4 chars/token en español) y ~50 tokens de solapamiento.
MAX_CARACTERES_VENTANA = 800
SOLAPAMIENTO_CARACTERES = 200

# Líneas que arrancan un bloque numerado o con palabra clave de sección.
_PATRON_SECCION = re.compile(
    r"^(cap[íi]tulo|secci[óo]n|art[íi]culo|t[íi]tulo|m[óo]dulo)\b"
    r"|^(\d+(\.\d+)*)[\s\.\)]"
    r"|^([IVXLC]+)[\s\.\)]",
    re.IGNORECASE,
)


def normalizar(texto: str) -> str:
    """Colapsa espacios en blanco para que el hash sea estable ante reformateos."""
    return " ".join(texto.split())


def hash_contenido(texto: str) -> str:
    """SHA-256 del contenido normalizado: contenido idéntico → mismo id."""
    return hashlib.sha256(normalizar(texto).encode("utf-8")).hexdigest()


def _es_titulo_seccion(linea: str) -> bool:
    """Heurística tolerante: línea corta, con letras, numerada o mayormente en mayúsculas."""
    limpia = linea.strip()
    if not limpia or len(limpia) > 100:
        return False
    letras = [c for c in limpia if c.isalpha()]
    if not letras:
        return False
    mayusculas = sum(1 for c in letras if c.isupper())
    return bool(_PATRON_SECCION.match(limpia)) or mayusculas / len(letras) >= 0.7


def dividir_secciones(texto: str) -> list[tuple[str | None, str]]:
    """Divide un texto en (título de sección, cuerpo).

    Las líneas que parecen encabezados abren una sección; el texto anterior a
    la primera sección queda como cuerpo con sección `None`.
    """
    secciones: list[tuple[str | None, list[str]]] = [(None, [])]
    for linea in texto.splitlines():
        if _es_titulo_seccion(linea):
            secciones.append((linea.strip(), []))
        else:
            secciones[-1][1].append(linea)
    return [
        (titulo, "\n".join(cuerpo).strip())
        for titulo, cuerpo in secciones
        if titulo is not None or "\n".join(cuerpo).strip()
    ]


def _ventanas(texto: str) -> list[str]:
    """Divide un texto largo en ventanas de hasta MAX_CARACTERES con solapamiento."""
    if len(texto) <= MAX_CARACTERES_VENTANA:
        return [texto]
    ventanas = []
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + MAX_CARACTERES_VENTANA, len(texto))
        if fin < len(texto):  # cortar en el último espacio para no partir palabras
            corte = texto.rfind(" ", inicio, fin)
            if corte > inicio:
                fin = corte
        ventanas.append(texto[inicio:fin].strip())
        if fin >= len(texto):
            break
        inicio = fin - SOLAPAMIENTO_CARACTERES
    return [v for v in ventanas if v]


def fragmentar(
    texto: str,
    *,
    tipo: str,
    url: str,
    titulo: str,
    fecha: str | None = None,
) -> list[Fragmento]:
    """Convierte un documento en fragmentos que preservan sus secciones.

    Cada fragmento lleva como contenido el título del documento, el título de
    su sección y la ventana de texto correspondiente; su id es el hash de ese
    contenido (deduplicación automática en re-ingestas).
    """
    fragmentos: list[Fragmento] = []
    for titulo_seccion, cuerpo in dividir_secciones(texto):
        for ventana in _ventanas(cuerpo):
            partes = [p for p in (titulo, titulo_seccion, ventana) if p]
            contenido = "\n\n".join(partes)
            fragmentos.append(
                Fragmento(
                    id=hash_contenido(contenido),
                    contenido=contenido,
                    tipo=tipo,
                    url=url,
                    titulo=titulo,
                    fecha=fecha,
                )
            )
    return fragmentos
