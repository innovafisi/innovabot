"""Tarea 2.2: descarga y extracción de PDFs (pdfplumber) con chunking por secciones.

Verificación (tasks.md): un PDF fixture produce fragmentos que preservan
secciones, y un PDF ilegible (sin texto) queda registrado y excluido sin
detener el procesamiento.
"""

from pathlib import Path

import httpx

from app.ingestion.pdfs import (
    PdfIlegible,
    encontrar_enlaces_pdf,
    fragmentar_pdf,
    procesar_pdfs,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF_VALIDO = (FIXTURES / "pdf_valido.pdf").read_bytes()
PDF_ILEGIBLE = (FIXTURES / "pdf_ilegible.pdf").read_bytes()

URL_VALIDO = "https://sistemas.unmsm.edu.pe/site/images/pdf/plan_estudios.pdf"
URL_ILEGIBLE = "https://sistemas.unmsm.edu.pe/site/images/pdf/escaneado.pdf"


def test_fragmentos_preservan_secciones() -> None:
    """Cada sección del PDF genera su(s) fragmento(s) con el encabezado presente."""
    fragmentos = fragmentar_pdf(PDF_VALIDO, url=URL_VALIDO, titulo="Plan de Estudios")

    assert len(fragmentos) >= 3  # al menos un fragmento por sección
    assert all(f.tipo == "pdf" for f in fragmentos)
    assert all(f.url == URL_VALIDO for f in fragmentos)
    assert all(f.titulo == "Plan de Estudios" for f in fragmentos)

    contenidos = "\n".join(f.contenido for f in fragmentos)
    for seccion in ("SECCION 1", "SECCION 2", "SECCION 3"):
        assert seccion in contenidos
    # el cuerpo de cada sección viaja dentro de su fragmento
    assert "sistemas de informacion" in contenidos
    assert "grado de bachiller" in contenidos
    assert "ingenieria de software" in contenidos


def test_pdf_ilegible_lanza_excepcion_con_url() -> None:
    """Un PDF sin texto extraíble se detecta como ilegible (con su URL)."""
    try:
        fragmentar_pdf(PDF_ILEGIBLE, url=URL_ILEGIBLE, titulo="Escaneado")
        raise AssertionError("Se esperaba PdfIlegible")
    except PdfIlegible as exc:
        assert URL_ILEGIBLE in str(exc)


def _cliente_mock() -> httpx.Client:
    def controlador(peticion: httpx.Request) -> httpx.Response:
        if peticion.url == URL_VALIDO:
            return httpx.Response(200, content=PDF_VALIDO)
        return httpx.Response(200, content=PDF_ILEGIBLE)

    return httpx.Client(transport=httpx.MockTransport(controlador))


def test_pdf_ilegible_registrado_y_excluido_sin_detener() -> None:
    """El ilegible queda registrado; el válido se procesa con normalidad."""
    with _cliente_mock() as cliente:
        fragmentos, errores = procesar_pdfs(cliente, [URL_ILEGIBLE, URL_VALIDO])

    assert len(errores) == 1
    assert URL_ILEGIBLE in errores[0]
    assert "ilegible" in errores[0]
    assert all(f.url == URL_VALIDO for f in fragmentos)
    assert fragmentos  # el válido sí aportó fragmentos


def test_error_de_descarga_registrado_y_continua() -> None:
    """Una URL que falla se registra y no detiene los demás PDFs."""
    def controlador(peticion: httpx.Request) -> httpx.Response:
        if peticion.url == URL_VALIDO:
            return httpx.Response(200, content=PDF_VALIDO)
        return httpx.Response(404, text="no encontrado")

    with httpx.Client(transport=httpx.MockTransport(controlador)) as cliente:
        fragmentos, errores = procesar_pdfs(cliente, [URL_ILEGIBLE, URL_VALIDO])

    assert len(errores) == 1
    assert "404" in errores[0]
    assert fragmentos


def test_encontrar_enlaces_pdf() -> None:
    """Detecta enlaces .pdf relativos y absolutos, deduplicando."""
    html = """
    <a href="/site/images/pdf/a.pdf">Plan A</a>
    <a href="/site/images/pdf/a.pdf">Plan A (repetido)</a>
    <a href="https://otro.unmsm.edu.pe/b.pdf">Otro</a>
    <a href="/site/noticias/35-importante">No es PDF</a>
    """
    enlaces = encontrar_enlaces_pdf(html, "https://sistemas.unmsm.edu.pe/site/")
    assert enlaces == [
        "https://sistemas.unmsm.edu.pe/site/images/pdf/a.pdf",
        "https://otro.unmsm.edu.pe/b.pdf",
    ]
