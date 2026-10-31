"""Tareas 2.2 y 5.1/5.2: descarga y extracción de PDFs (pdfplumber) con chunking.

Verificación (tasks.md): un PDF fixture produce fragmentos que preservan
secciones, y un PDF ilegible (sin texto) queda registrado y excluido sin
detener el procesamiento. Además, la ingesta solo descarga de hosts permitidos
y verifica que lo descargado sea un PDF real (anti-SSRF, OWASP LLM04).
"""

from pathlib import Path

import httpx
import pytest

from app.ingestion import pdfs
from app.ingestion.pdfs import (
    PdfIlegible,
    encontrar_enlaces_pdf,
    es_pdf,
    fragmentar_pdf,
    procesar_pdfs,
    url_permitida,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PDF_VALIDO = (FIXTURES / "pdf_valido.pdf").read_bytes()
PDF_ILEGIBLE = (FIXTURES / "pdf_ilegible.pdf").read_bytes()

URL_VALIDO = "https://sistemas.unmsm.edu.pe/site/images/pdf/plan_estudios.pdf"
URL_ILEGIBLE = "https://sistemas.unmsm.edu.pe/site/images/pdf/escaneado.pdf"


@pytest.fixture(autouse=True)
def _sin_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los unit tests nunca resuelven DNS real: `_resolver_host` da una IP pública."""
    monkeypatch.setattr(pdfs, "_resolver_host", lambda host: ["93.184.216.34"])


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


# --- Anti-SSRF: url_permitida y es_pdf (tareas 5.1/5.2) ----------------------


def test_url_permitida_host_del_portal() -> None:
    """Una URL del portal oficial es permitida."""
    assert url_permitida(URL_VALIDO) is True


def test_url_permitida_rechaza_host_ajeno() -> None:
    """Un host fuera de la allowlist se rechaza."""
    assert url_permitida("https://evil.example/x.pdf") is False


def test_url_permitida_rechaza_ip_privada_literal() -> None:
    """Una IP privada literal nunca está en la allowlist."""
    assert url_permitida("http://192.168.0.168/x.pdf") is False


def test_url_permitida_rechaza_loopback() -> None:
    """El loopback literal se rechaza."""
    assert url_permitida("http://127.0.0.1/x.pdf") is False


def test_url_permitida_rechaza_host_permitido_que_resuelve_interno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un host permitido cuya DNS apunta a la VPC se rechaza (anti-SSRF)."""
    monkeypatch.setattr(pdfs, "_resolver_host", lambda host: ["192.168.0.168"])
    assert url_permitida(URL_VALIDO) is False


def test_url_permitida_rechaza_esquema_no_web() -> None:
    """Solo http/https son esquemas válidos."""
    assert url_permitida("ftp://sistemas.unmsm.edu.pe/x.pdf") is False


def test_url_permitida_acepta_subdominio() -> None:
    """Un subdominio de un host permitido es aceptado."""
    assert url_permitida("https://www.unmsm.edu.pe/x.pdf") is True


def test_url_permitida_resolucion_fallida(monkeypatch: pytest.MonkeyPatch) -> None:
    """Si la resolución DNS falla, la URL no se permite."""
    def falla(host: str) -> list[str]:
        raise OSError("fallo de resolución")

    monkeypatch.setattr(pdfs, "_resolver_host", falla)
    assert url_permitida(URL_VALIDO) is False


def test_es_pdf_detecta_cabecera() -> None:
    """Detecta la cabecera %PDF- dentro de los primeros 1 KB."""
    assert es_pdf(PDF_VALIDO) is True
    assert es_pdf(b"<html>no soy un pdf</html>") is False


def test_procesar_pdfs_rechaza_host_ajeno_sin_descargar() -> None:
    """Una URL de host ajeno se registra y NO se descarga; el PDF válido sigue."""
    llamadas: list[str] = []
    url_ajena = "https://evil.example/x.pdf"

    def controlador(peticion: httpx.Request) -> httpx.Response:
        llamadas.append(str(peticion.url))
        return httpx.Response(200, content=PDF_VALIDO)

    with httpx.Client(transport=httpx.MockTransport(controlador)) as cliente:
        fragmentos, errores = procesar_pdfs(cliente, [url_ajena, URL_VALIDO])

    assert any("no permitida" in e and url_ajena in e for e in errores)
    assert url_ajena not in llamadas  # no se hizo petición HTTP para el host ajeno
    assert URL_VALIDO in llamadas
    assert fragmentos


def test_procesar_pdfs_descarta_contenido_no_pdf() -> None:
    """Una URL del portal que devuelve HTML se descarta sin detener el resto."""
    url_html = "https://sistemas.unmsm.edu.pe/site/images/pdf/falso.pdf"

    def controlador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == url_html:
            return httpx.Response(200, content=b"<html>no soy un pdf</html>")
        return httpx.Response(200, content=PDF_VALIDO)

    with httpx.Client(transport=httpx.MockTransport(controlador)) as cliente:
        fragmentos, errores = procesar_pdfs(cliente, [url_html, URL_VALIDO])

    assert any("no es un PDF" in e and url_html in e for e in errores)
    assert all(f.url == URL_VALIDO for f in fragmentos)
    assert fragmentos
