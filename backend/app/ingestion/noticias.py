"""Scraper de noticias del portal FISI (sistemas.unmsm.edu.pe).

Extrae título, contenido, fecha y URL de las noticias del listado del portal.
Los selectores viven centralizados en `SELECTORES` (listas ordenadas: se usa
el primer selector que matchea) para tolerar cambios del HTML ajustando un
solo lugar. Los fallos por página se registran sin detener el scraper.
"""

import logging
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.modelos import Fragmento
from app.ingestion.chunking import fragmentar

logger = logging.getLogger("innovabot")

PORTAL_FISI = "https://sistemas.unmsm.edu.pe"
# Listado de noticias de la categoría "Importante" (página con las noticias completas).
URL_LISTADO_NOTICIAS = f"{PORTAL_FISI}/site/noticias/35-importante"

# Selectores centralizados y tolerantes: por campo se prueban en orden hasta
# que uno matchee. Si el portal cambia su HTML, se ajusta aquí y solo aquí.
SELECTORES: dict[str, list[str]] = {
    "item": ["div.news_item_c", "article"],
    "titulo": ["h2.article_title a", "h2 a", "a.titulo"],
    "contenido": ["div.newsitem_text", "div.article-content"],
    "fecha": ["time[datetime]", "[itemprop='datePublished']", ".newsitem_date"],
}

# Fecha textual en español dentro del contenido, SOLO cuando el texto la marca
# explícitamente como fecha de publicación ("publicado el ..."). El portal FISI
# no expone la fecha como dato estructurado; extraer cualquier fecha suelta del
# cuerpo daría metadatos falsos (plazos, vigencias), así que sin marcador → None.
_PATRON_FECHA = re.compile(
    r"publicad[oa] el\s*:?\s*(\d{1,2}) de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"setiembre|septiembre|octubre|noviembre|diciembre) de (\d{4})",
    re.IGNORECASE,
)
_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _primer(sopa: BeautifulSoup, selectores: list[str]):
    """Primer nodo que matchea alguno de los selectores (tolerancia a cambios)."""
    for selector in selectores:
        nodo = sopa.select_one(selector)
        if nodo is not None:
            return nodo
    return None


def _extraer_fecha(item: BeautifulSoup) -> str | None:
    """Fecha de publicación en ISO, si el item la expone (estructurada o textual)."""
    nodo = _primer(item, SELECTORES["fecha"])
    if nodo is not None:
        datetime_attr = nodo.get("datetime") or nodo.get("content")
        if datetime_attr:
            try:
                return date.fromisoformat(str(datetime_attr)[:10]).isoformat()
            except ValueError:
                pass
    # El HTML real parte las frases en varias líneas: se normaliza antes de buscar.
    texto = " ".join(item.get_text(" ", strip=True).split())
    coincidencia = _PATRON_FECHA.search(texto)
    if coincidencia:
        dia = int(coincidencia.group(1))
        mes = coincidencia.group(2).lower()
        anio = int(coincidencia.group(3))
        return date(anio, _MESES[mes], dia).isoformat()
    return None


def extraer_noticias(html: str, base_url: str = PORTAL_FISI) -> list[dict]:
    """Extrae las noticias de una página de listado del portal FISI.

    Los items sin título, contenido o URL se descartan (datos incompletos).
    """
    sopa = BeautifulSoup(html, "html.parser")
    noticias: list[dict] = []
    for item in sopa.select(", ".join(SELECTORES["item"])):
        enlace = _primer(item, SELECTORES["titulo"])
        nodo_contenido = _primer(item, SELECTORES["contenido"])
        if enlace is None or nodo_contenido is None:
            continue
        titulo = enlace.get_text(" ", strip=True)
        contenido = nodo_contenido.get_text(" ", strip=True)
        href = enlace.get("href", "")
        if not titulo or not contenido or not href:
            continue
        noticias.append(
            {
                "titulo": titulo,
                "contenido": contenido,
                "fecha": _extraer_fecha(item),
                "url": urljoin(base_url, href),
            }
        )
    return noticias


def scrapear_noticias(
    cliente_http,
    urls_listado: list[str] | None = None,
    limite: int | None = None,
) -> tuple[list[dict], list[str]]:
    """Scrapea los listados de noticias; devuelve (noticias, errores por página).

    Un fallo en una página (red, HTTP, HTML cambiado) se registra y el scraper
    continúa con las demás. Si una página no aporta noticias, también se
    registra (alerta del design: ejecución con 0 noticias).
    """
    urls = urls_listado or [URL_LISTADO_NOTICIAS]
    noticias: list[dict] = []
    errores: list[str] = []
    for url in urls:
        try:
            respuesta = cliente_http.get(url)
            respuesta.raise_for_status()
            extraidas = extraer_noticias(respuesta.text, base_url=url)
        except Exception as exc:  # noqa: BLE001 - el scraper registra y continúa
            errores.append(f"{url}: {exc}")
            logger.error("Error scrapeando %s: %s", url, exc)
            continue
        if not extraidas:
            errores.append(f"{url}: no se extrajo ninguna noticia")
            logger.warning("La página %s no aportó noticias (¿cambió el HTML?)", url)
        noticias.extend(extraidas)
    if limite is not None:
        noticias = noticias[:limite]
    return noticias, errores


def a_fragmentos(noticias: list[dict]) -> list[Fragmento]:
    """Convierte noticias extraídas en fragmentos listos para indexar."""
    fragmentos: list[Fragmento] = []
    for noticia in noticias:
        fragmentos.extend(
            fragmentar(
                noticia["contenido"],
                tipo="noticia",
                url=noticia["url"],
                titulo=noticia["titulo"],
                fecha=noticia["fecha"],
            )
        )
    return fragmentos
