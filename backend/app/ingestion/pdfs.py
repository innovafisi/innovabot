"""Descarga y extracción de PDFs del portal FISI (pdfplumber).

Extrae el texto de cada PDF y lo fragmenta por secciones con solapamiento
(ver `chunking.py`). Un PDF ilegible (escaneado, sin texto extraíble) se
registra con su URL y queda excluido, sin detener la ingesta (design: OCR
fuera de alcance).
"""

import io
import ipaddress
import logging
import re
import socket
from urllib.parse import urljoin, urlparse

import pdfplumber
from bs4 import BeautifulSoup

from app.core.modelos import Fragmento
from app.core.settings import get_settings
from app.ingestion.chunking import fragmentar, normalizar

logger = logging.getLogger("innovabot")

# Páginas del portal FISI donde se buscan enlaces a PDFs (planes de estudio,
# reglamentos, directivas, tarifarios). Ajustable por el equipo.
PAGINAS_CON_PDFS = [
    "https://sistemas.unmsm.edu.pe/site/estudiantes/tramites-posgrado",
    "https://sistemas.unmsm.edu.pe/site/pagos-exigidos-a-los-alumnos",
]

# Dominios oficiales desde los que se permite descargar PDFs (fijos). La
# allowlist se completa con `INGESTA_HOSTS_PERMITIDOS` (settings).
HOSTS_PORTAL = ["sistemas.unmsm.edu.pe", "unmsm.edu.pe"]


def hosts_permitidos() -> list[str]:
    """Allowlist de hosts de descarga: dominios oficiales + los extra de settings."""
    return HOSTS_PORTAL + get_settings().hosts_ingesta_extra


def _resolver_host(host: str) -> list[str]:
    """IPs a las que resuelve `host`.

    Indirecto módulo-level a propósito: los unit tests lo monkeypatchean para no
    resolver DNS real.
    """
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def _es_ip_interna(ip_texto: str) -> bool:
    """True si la IP es privada, loopback, link-local, reservada o multicast."""
    try:
        ip = ipaddress.ip_address(ip_texto)
    except ValueError:
        # Texto que no parsea como IP: por seguridad se trata como interna.
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def url_permitida(url: str, hosts: list[str] | None = None) -> bool:
    """True si `url` apunta a un host de la allowlist que resuelve a IPs públicas.

    Defensa anti-SSRF: rechaza esquemas no web, hosts fuera de la allowlist
    (incluidas IPs literales) y hosts de la allowlist cuya resolución apunte a
    direcciones internas de la VPC.
    """
    hosts = hosts if hosts is not None else hosts_permitidos()
    partes = urlparse(url)
    if partes.scheme not in ("http", "https"):
        return False
    host = (partes.hostname or "").lower()
    if not host:
        return False
    # Host permitido o subdominio suyo (las IPs literales nunca están en la lista).
    if not any(host == h.lower() or host.endswith("." + h.lower()) for h in hosts):
        return False
    try:
        ips = _resolver_host(host)
    except Exception:  # noqa: BLE001 - resolución fallida = no permitida
        return False
    if any(_es_ip_interna(ip) for ip in ips):
        return False
    return True


def es_pdf(contenido: bytes) -> bool:
    """True si `contenido` parece un PDF (cabecera `%PDF-` en los primeros 1 KB)."""
    return b"%PDF-" in contenido[:1024]


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
        if not url_permitida(url):
            errores.append(f"{url}: URL no permitida por la política de descarga (anti-SSRF)")
            logger.warning("URL no permitida (anti-SSRF): %s", url)
            continue
        try:
            pdf_bytes = descargar_pdf(cliente_http, url)
            if not es_pdf(pdf_bytes):
                errores.append(f"{url}: el contenido descargado no es un PDF")
                logger.warning("Contenido no PDF descartado: %s", url)
                continue
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
