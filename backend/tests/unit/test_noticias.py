"""Tarea 2.1: scraper de noticias del portal FISI.

Verificación (tasks.md): test contra HTML fixture que extrae título,
contenido, fecha y URL, y una página con error se registra sin detener
el scraper.
"""

from pathlib import Path

import httpx

from app.ingestion.noticias import extraer_noticias, scrapear_noticias

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
HTML_LISTADO = (FIXTURES / "noticias_fisi.html").read_text(encoding="utf-8")
URL_LISTADO = "https://sistemas.unmsm.edu.pe/site/noticias/35-importante"
URL_ROTA = "https://sistemas.unmsm.edu.pe/site/noticias/99-inexistente"


def test_extrae_titulo_contenido_fecha_url() -> None:
    """El scraper extrae los 4 campos de cada noticia del HTML fixture."""
    noticias = extraer_noticias(HTML_LISTADO, base_url=URL_LISTADO)

    assert len(noticias) == 3  # el item sin contenido se descarta
    primera = noticias[0]
    assert primera["titulo"] == "Microcursos gratuitos: “Aprende con INDECOPI”"
    assert "microcursos virtuales gratuitos" in primera["contenido"]
    assert primera["url"] == (
        "https://sistemas.unmsm.edu.pe/site/noticias/35-importante/"
        "1911-microcursos-gratuitos-aprende-con-indecopi"
    )
    # fecha textual en español dentro del contenido → ISO
    assert primera["fecha"] == "2026-10-20"


def test_fecha_ausente_es_none_y_setiembre_se_normaliza() -> None:
    """Sin fecha expuesta el campo queda en None; 'setiembre' se normaliza a 09."""
    noticias = extraer_noticias(HTML_LISTADO, base_url=URL_LISTADO)
    assert noticias[1]["fecha"] is None
    assert noticias[2]["fecha"] == "2026-09-05"


def _cliente_mock() -> httpx.Client:
    def controlador(peticion: httpx.Request) -> httpx.Response:
        if peticion.url == URL_LISTADO:
            return httpx.Response(200, text=HTML_LISTADO)
        return httpx.Response(500, text="error del servidor")

    return httpx.Client(transport=httpx.MockTransport(controlador))


def test_pagina_con_error_se_registra_y_no_detiene() -> None:
    """Un fallo en una página se registra y el scraper sigue con las demás."""
    with _cliente_mock() as cliente:
        noticias, errores = scrapear_noticias(cliente, urls_listado=[URL_ROTA, URL_LISTADO])

    assert len(noticias) == 3
    assert len(errores) == 1
    assert URL_ROTA in errores[0]
    assert "500" in errores[0]


def test_limite_restringe_cortesamente_el_scrapeo() -> None:
    """El límite permite ejecuciones educadas (solo las primeras N noticias)."""
    with _cliente_mock() as cliente:
        noticias, errores = scrapear_noticias(cliente, urls_listado=[URL_LISTADO], limite=2)

    assert len(noticias) == 2
    assert errores == []


def test_pagina_sin_noticias_genera_alerta() -> None:
    """Una página que no aporta noticias queda registrada (alerta del design)."""
    def controlador(peticion: httpx.Request) -> httpx.Response:
        assert peticion.url == URL_LISTADO
        return httpx.Response(200, text="<html><body>Sin noticias aquí</body></html>")

    with httpx.Client(transport=httpx.MockTransport(controlador)) as cliente:
        noticias, errores = scrapear_noticias(cliente, urls_listado=[URL_LISTADO])

    assert noticias == []
    assert len(errores) == 1
    assert "no se extrajo ninguna noticia" in errores[0]
