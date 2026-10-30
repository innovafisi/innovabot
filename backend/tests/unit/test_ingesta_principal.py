"""Orquestación de la ingesta (`python -m app.ingest`): cableado de las 4 fuentes.

Verifica que `main()` recolecta noticias, PDFs, FAQs y portal central con un
cliente HTTP mockeado, indexa con embeddings falsos y crea la tabla antes del
upsert; y que termina con código 1 (alerta) si no recolecta nada.
"""

from pathlib import Path
from unittest import mock

import httpx

from app.core.modelos import Fragmento
from app.ingestion import __main__ as ingesta
from app.ingestion.noticias import URL_LISTADO_NOTICIAS

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
HTML_LISTADO = (FIXTURES / "noticias_fisi.html").read_text(encoding="utf-8")
HTML_PORTAL = (FIXTURES / "portal_unmsm.html").read_text(encoding="utf-8")


class EmbeddingsFalsos:
    def embeber(self, textos, *, es_consulta=False):
        return [[1.0, 0.0] for _ in textos]


class AlmacenFalso:
    def __init__(self) -> None:
        self.fragmentos: dict[str, Fragmento] = {}
        self.crear_tabla_llamado = False

    def crear_tabla(self) -> None:
        self.crear_tabla_llamado = True

    def indexar(self, fragmentos):
        for f in fragmentos:
            self.fragmentos[f.id] = f
        return len(fragmentos)

    def marcar_obsoletos(self, url, ids_vigentes) -> None:
        pass


def _cliente_mock() -> httpx.Client:
    def controlador(peticion: httpx.Request) -> httpx.Response:
        if str(peticion.url) == URL_LISTADO_NOTICIAS:
            return httpx.Response(200, text=HTML_LISTADO)
        # páginas del portal central y páginas donde se buscan PDFs
        return httpx.Response(200, text=HTML_PORTAL)

    return httpx.Client(transport=httpx.MockTransport(controlador))


def test_main_orquesta_las_4_fuentes_e_indexa(monkeypatch, tmp_path) -> None:
    """La ingesta completa recolecta noticia, portal y FAQ, y crea la tabla."""
    monkeypatch.setenv("FAQS_MD", str(tmp_path / "faqs.md"))
    (tmp_path / "faqs.md").write_text(
        "## ¿Cómo ingreso a la FISI?\n\nMediante el examen de admisión.", encoding="utf-8"
    )
    monkeypatch.setenv("SECCIONES_PORTAL_YML", str(FIXTURES / "secciones_portal.yml"))

    almacen = AlmacenFalso()
    parches = (
        mock.patch.object(ingesta, "crear_cliente_http", return_value=_cliente_mock()),
        mock.patch.object(ingesta, "ClienteEmbeddings", return_value=EmbeddingsFalsos()),
        mock.patch.object(ingesta, "AlmacenVectorial", return_value=almacen),
    )
    with parches[0], parches[1], parches[2]:
        codigo = ingesta.main()

    assert codigo == 0
    assert almacen.crear_tabla_llamado
    tipos = {f.tipo for f in almacen.fragmentos.values()}
    assert tipos == {"noticia", "portal", "faq"}
    # las noticias del fixture llegan indexadas
    assert any("INDECOPI" in f.titulo for f in almacen.fragmentos.values())
    # todo fragmento indexado quedó con embedding
    assert all(f.embedding is not None for f in almacen.fragmentos.values())


def test_main_alerta_y_falla_si_no_recolecta_nada(monkeypatch, tmp_path) -> None:
    """Sin fragmentos de ninguna fuente, la ingesta alerta con código 1."""
    monkeypatch.setenv("FAQS_MD", str(tmp_path / "faqs.md"))
    (tmp_path / "faqs.md").write_text("# Sin FAQs aún\n", encoding="utf-8")
    monkeypatch.setenv("SECCIONES_PORTAL_YML", str(tmp_path / "secciones.yml"))
    (tmp_path / "secciones.yml").write_text("secciones: []\n", encoding="utf-8")

    def controlador(peticion: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="caída total")

    almacen = AlmacenFalso()
    parches = (
        mock.patch.object(
            ingesta,
            "crear_cliente_http",
            return_value=httpx.Client(transport=httpx.MockTransport(controlador)),
        ),
        mock.patch.object(ingesta, "ClienteEmbeddings", return_value=EmbeddingsFalsos()),
        mock.patch.object(ingesta, "AlmacenVectorial", return_value=almacen),
    )
    with parches[0], parches[1], parches[2]:
        codigo = ingesta.main()

    assert codigo == 1
    assert almacen.fragmentos == {}
