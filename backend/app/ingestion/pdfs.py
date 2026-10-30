"""Descarga y extracción de PDFs del portal FISI (pdfplumber).

Extrae el texto de cada PDF y lo fragmenta por secciones con solapamiento
(ver `chunking.py`). Un PDF ilegible (escaneado, sin texto extraíble) se
registra con su URL y queda excluido, sin detener la ingesta (design: OCR
fuera de alcance).
"""

import io
import logging
import re
from urllib.parse import urljoin

import pdfplumber
from bs4 import BeautifulSoup

from app.core.modelos import Fragmento
from app.ingestion.chunking import fragmentar, normalizar

logger = logging.getLogger("innovabot")

# Páginas del portal FISI donde se buscan enlaces a PDFs (planes de estudio,
# reglamentos, directivas, tarifarios). Ajustable por el equipo.
PAGINAS_CON_PDFS = [
    "https://sistemas.unmsm.edu.pe/site/estudiantes/tramites-posgrado",
    "https://sistemas.unmsm.edu.pe/site/pagos-exigidos-a-los-alumnos",
]


class PdfIlegible(ValueError):
    """El PDF no tiene texto extraíble (escaneado o corrupto)."""


def encontrar_enlaces_pdf(html: str, base_url: str) -> list[str]:
    """URLs absolutas de los enlaces a .pdf que aparecen en una página del portal."""
    sopa = BeautifulSoup(html, "html.parser")
    enlaces: list[str] = []
    for etiqueta in sopa.find_all("a", href=True):
        href = etiqueta["href"].strip()
        if ".pdf" in href.lower():
            enlaces.append(urljoin(base_url, href))
    # deduplicar preservando el orden
    return list(dict.fromkeys(enlaces))


def descargar_pdf(cliente_http, url: str) -> bytes:
    """Descarga un PDF; lanza si el servidor responde con error."""
    respuesta = cliente_http.get(url)
    respuesta.raise_for_status()
    return respuesta.content


def extraer_texto(pdf_bytes: bytes) -> str:
    """Texto completo del PDF (una página por bloque), con pdfplumber."""
    paginas: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pagina in pdf.pages:
            paginas.append(pagina.extract_text() or "")
    return "\n".join(paginas)


def fragmentar_pdf(
    pdf_bytes: bytes,
    *,
    url: str,
    titulo: str,
    fecha: str | None = None,
) -> list[Fragmento]:
    """Fragmenta un PDF por secciones; lanza `PdfIlegible` si no hay texto."""
    texto = extraer_texto(pdf_bytes)
    if not normalizar(texto):
        raise PdfIlegible(url)
    return fragmentar(texto, tipo="pdf", url=url, titulo=titulo, fecha=fecha)


def _titulo_desde_url(url: str) -> str:
    """Nombre de archivo como título tolerable cuando no hay uno mejor."""
    ultimo = url.rstrip("/").split("/")[-1]
    return re.sub(r"\.pdf$", "", ultimo, flags=re.IGNORECASE).replace("_", " ").strip() or url


def procesar_pdfs(
    cliente_http,
    urls: list[str],
    limite: int | None = None,
) -> tuple[list[Fragmento], list[str]]:
    """Descarga y fragmenta cada PDF; devuelve (fragmentos, errores por PDF).

    Los fallos de descarga y los PDFs ilegibles se registran con su URL y se
    excluyen, sin detener el procesamiento de los demás.
    """
    fragmentos: list[Fragmento] = []
    errores: list[str] = []
    for url in urls[:limite] if limite else urls:
        try:
            pdf_bytes = descargar_pdf(cliente_http, url)
            fragmentos.extend(
                fragmentar_pdf(pdf_bytes, url=url, titulo=_titulo_desde_url(url))
            )
        except PdfIlegible:
            errores.append(f"{url}: PDF ilegible (sin texto extraíble)")
            logger.warning("PDF ilegible excluido: %s", url)
        except Exception as exc:  # noqa: BLE001 - se registra y continúa con los demás
            errores.append(f"{url}: {exc}")
            logger.error("Error procesando PDF %s: %s", url, exc)
    return fragmentos, errores
