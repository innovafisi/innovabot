"""Scrapeo de las secciones configurables del portal central UNMSM.

La lista de secciones vive en `data/secciones_portal.yml` (nombre + URL);
solo esas secciones se ingieren. Cada página se convierte en un fragmento
`tipo=portal` con la fecha de consulta como fecha (el portal central no
publica fecha de publicación por página).
"""

import logging
from datetime import date
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from app.core.modelos import Fragmento
from app.ingestion.chunking import fragmentar

logger = logging.getLogger("innovabot")

# Etiquetas sin contenido útil para el retrieval.
_ETIQUETAS_DESCARTABLES = ["script", "style", "nav", "header", "footer", "aside", "form"]


def cargar_secciones(ruta_yml: str | Path) -> list[dict]:
    """Carga la lista de secciones configuradas: `[{"nombre": ..., "url": ...}]`."""
    datos = yaml.safe_load(Path(ruta_yml).read_text(encoding="utf-8"))
    secciones = datos.get("secciones", []) if isinstance(datos, dict) else []
    return [s for s in secciones if isinstance(s, dict) and s.get("nombre") and s.get("url")]


def extraer_pagina(html: str) -> tuple[str, str]:
    """Extrae (título, texto principal) de una página, de forma tolerante.

    Prefiere el contenido de `<main>`/`<article>`; si no existen, usa el body
    completo tras descartar scripts, estilos y navegación.
    """
    sopa = BeautifulSoup(html, "html.parser")
    for etiqueta in sopa(_ETIQUETAS_DESCARTABLES):
        etiqueta.decompose()
    titulo = ""
    if sopa.h1 is not None:
        titulo = sopa.h1.get_text(" ", strip=True)
    elif sopa.title is not None:
        titulo = sopa.title.get_text(" ", strip=True)
    principal = sopa.find("main") or sopa.find("article") or sopa.find("body") or sopa
    return titulo, principal.get_text("\n", strip=True)


def scrapear_secciones(
    cliente_http,
    secciones: list[dict],
    fecha_consulta: str | None = None,
) -> tuple[list[Fragmento], list[str]]:
    """Scrapea las secciones configuradas; devuelve (fragmentos, errores por sección).

    Un fallo por sección se registra y se continúa con las demás.
    """
    fecha = fecha_consulta or date.today().isoformat()
    fragmentos: list[Fragmento] = []
    errores: list[str] = []
    for seccion in secciones:
        url = seccion["url"]
        try:
            respuesta = cliente_http.get(url)
            respuesta.raise_for_status()
            titulo, texto = extraer_pagina(respuesta.text)
            if not texto:
                raise ValueError("página sin contenido textual")
        except Exception as exc:  # noqa: BLE001 - se registra y continúa
            errores.append(f"{url}: {exc}")
            logger.error("Error scrapeando la sección %s: %s", url, exc)
            continue
        fragmentos.extend(
            fragmentar(
                texto,
                tipo="portal",
                url=url,
                titulo=titulo or seccion["nombre"],
                fecha=fecha,
            )
        )
    return fragmentos, errores
