"""Tarea 2.4: scrapeo de las secciones configurables del portal central UNMSM.

Verificación (tasks.md): solo se ingieren las secciones configuradas en el YAML.
"""

from pathlib import Path

import httpx

from app.ingestion.portal import cargar_secciones, extraer_pagina, scrapear_secciones

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
HTML_PORTAL = (FIXTURES / "portal_unmsm.html").read_text(encoding="utf-8")
YAML_SECCIONES = FIXTURES / "secciones_portal.yml"

URL_ADMISION = "https://www.unmsm.edu.pe/formacion-academica/admision"
URL_VIDA = "https://www.unmsm.edu.pe/comunidad/vida-universitaria"
URL_NO_CONFIGURADA = "https://www.unmsm.edu.pe/investigacion/publicaciones"


def test_cargar_secciones_del_yaml() -> None:
    """El YAML se carga como lista de {nombre, url}."""
    secciones = cargar_secciones(YAML_SECCIONES)

    assert secciones == [
        {"nombre": "Admisión", "url": URL_ADMISION},
        {"nombre": "Vida universitaria", "url": URL_VIDA},
    ]


def test_solo_se_ingieren_las_secciones_configuradas() -> None:
    """Se scrapean exactamente las URLs del YAML, ni una más."""
    solicitadas: list[str] = []

    def controlador(peticion: httpx.Request) -> httpx.Response:
        solicitadas.append(str(peticion.url))
        if str(peticion.url) in (URL_ADMISION, URL_VIDA):
            return httpx.Response(200, text=HTML_PORTAL)
        return httpx.Response(404, text="no configurada")

    secciones = cargar_secciones(YAML_SECCIONES)
    with httpx.Client(transport=httpx.MockTransport(controlador)) as cliente:
        fragmentos, errores = scrapear_secciones(
            cliente, secciones, fecha_consulta="2026-10-30"
        )

    assert sorted(solicitadas) == sorted([URL_ADMISION, URL_VIDA])
    assert errores == []
    assert len(fragmentos) >= 2
    assert all(f.tipo == "portal" for f in fragmentos)
    assert all(f.fecha == "2026-10-30" for f in fragmentos)  # fecha de consulta
    assert {f.url for f in fragmentos} == {URL_ADMISION, URL_VIDA}


def test_extraer_pagina_descarta_navegacion_y_scripts() -> None:
    """El texto extraído excluye nav/footer/scripts y conserva el contenido principal."""
    titulo, texto = extraer_pagina(HTML_PORTAL)

    assert titulo == "Admisión"
    assert "examen de admisión" in texto
    assert "Oficina Central de Admisión" in texto
    assert "Inicio" not in texto  # nav descartada
    assert "rastreo" not in texto  # script descartado
    assert "derechos reservados" not in texto  # footer descartado


def test_error_por_seccion_registrado_sin_detener() -> None:
    """Una sección que falla se registra y las demás se ingieren."""
    def controlador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == URL_ADMISION:
            return httpx.Response(500, text="error")
        return httpx.Response(200, text=HTML_PORTAL)

    secciones = cargar_secciones(YAML_SECCIONES)
    with httpx.Client(transport=httpx.MockTransport(controlador)) as cliente:
        fragmentos, errores = scrapear_secciones(cliente, secciones)

    assert len(errores) == 1
    assert URL_ADMISION in errores[0]
    assert {f.url for f in fragmentos} == {URL_VIDA}
