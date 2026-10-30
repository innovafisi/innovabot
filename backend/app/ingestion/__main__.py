"""Entrypoint de la ingesta batch: `python -m app.ingest` (desde `backend/`).

Orquesta las 4 fuentes (noticias FISI, PDFs del portal, FAQs curadas y
secciones del portal central UNMSM), genera los embeddings y los indexa en
PostgreSQL (pgvector). Pensado para cron semanal y disparo manual.
"""

import logging
import ssl
from pathlib import Path

import certifi
import httpx

from app.core.clientes import AlmacenVectorial, ClienteEmbeddings
from app.core.modelos import Fragmento
from app.core.settings import get_settings
from app.ingestion import faqs, noticias, pdfs, portal
from app.ingestion.indexar import indexar

logger = logging.getLogger("innovabot")

# Identificación educada ante los portales que scrapeamos.
USER_AGENT = "innovabot-ingesta/0.1 (chatbot RAG de la FISI-UNMSM)"
# Cortesía: como máximo 5 PDFs por ejecución.
LIMITE_PDFS = 5

# El portal FISI sirve una cadena TLS incompleta: presenta un intermedio
# Sectigo equivocado y el correcto solo se resuelve por AIA (algo que OpenSSL
# no hace en Linux). Este PEM es ese intermedio PÚBLICO (descargado del AIA
# del certificado, crt.sectigo.com); no es un secret. Si el portal corrige su
# cadena, el archivo puede eliminarse junto con su uso aquí.
_INTERMEDIO_SECTIGO = Path(__file__).parent / "intermedio_sectigo.crt"


def crear_cliente_http() -> httpx.Client:
    """Cliente HTTP de la ingesta: verificación TLS estricta con certifi
    (+ intermedio público del portal FISI) y User Agent identificable."""
    contexto = ssl.create_default_context(cafile=certifi.where())
    if _INTERMEDIO_SECTIGO.exists():
        contexto.load_verify_locations(_INTERMEDIO_SECTIGO)
    return httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
        verify=contexto,
    )


def _recolectar(cliente_http: httpx.Client) -> tuple[list[Fragmento], list[str]]:
    """Recolecta fragmentos de las fuentes web (noticias, PDFs, portal central)."""
    fragmentos: list[Fragmento] = []
    errores: list[str] = []

    # 1. Noticias del portal FISI.
    extraidas, errs = noticias.scrapear_noticias(cliente_http)
    errores.extend(errs)
    fragmentos.extend(noticias.a_fragmentos(extraidas))
    logger.info("Noticias FISI: %d noticias → %d fragmentos", len(extraidas), len(fragmentos))

    # 2. PDFs del portal FISI: enlaces desde las páginas que publican documentos.
    urls_pdf: list[str] = []
    for pagina in pdfs.PAGINAS_CON_PDFS:
        try:
            respuesta = cliente_http.get(pagina)
            respuesta.raise_for_status()
            urls_pdf.extend(pdfs.encontrar_enlaces_pdf(respuesta.text, pagina))
        except Exception as exc:  # noqa: BLE001 - se registra y continúa
            errores.append(f"{pagina}: {exc}")
            logger.error("Error buscando PDFs en %s: %s", pagina, exc)
    urls_pdf = list(dict.fromkeys(urls_pdf))[:LIMITE_PDFS]
    fragmentos_pdf, errs = pdfs.procesar_pdfs(cliente_http, urls_pdf)
    errores.extend(errs)
    fragmentos.extend(fragmentos_pdf)
    logger.info("PDFs del portal: %d enlaces → %d fragmentos", len(urls_pdf), len(fragmentos_pdf))

    # 3. Secciones configuradas del portal central UNMSM.
    settings = get_settings()
    secciones = portal.cargar_secciones(settings.secciones_portal_yml)
    fragmentos_portal, errs = portal.scrapear_secciones(cliente_http, secciones)
    errores.extend(errs)
    fragmentos.extend(fragmentos_portal)
    logger.info(
        "Portal central: %d secciones → %d fragmentos", len(secciones), len(fragmentos_portal)
    )

    return fragmentos, errores


def main() -> int:
    """Ejecuta la ingesta completa. Devuelve 1 si no se indexó nada (alerta)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    with crear_cliente_http() as cliente:
        fragmentos, errores = _recolectar(cliente)

    # 4. FAQs curadas (archivo del repo, sin red).
    fragmentos_faq = faqs.cargar_faqs(settings.faqs_md)
    fragmentos.extend(fragmentos_faq)
    logger.info("FAQs curadas: %d fragmentos", len(fragmentos_faq))

    if errores:
        logger.warning("Fallos registrados durante la ingesta (%d):", len(errores))
        for error in errores:
            logger.warning("  - %s", error)
    if not fragmentos:
        logger.error(" ALERTA: la ingesta no recolectó ningún fragmento.")
        return 1

    # 5. Embeddings + upsert en pgvector + invalidación de obsoletos.
    almacen = AlmacenVectorial()
    almacen.crear_tabla()
    resumen = indexar(fragmentos, ClienteEmbeddings(), almacen)
    logger.info(
        "Indexación completa: %s fragmentos indexados, %s insertados nuevos, %s inválidos.",
        resumen["indexados"],
        resumen["insertados"],
        resumen["invalidos"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
