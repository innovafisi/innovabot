"""Tests de integración contra PostgreSQL con pgvector (tarea 4.1).

Requieren una base de datos de prueba con pgvector en `TEST_DATABASE_URL`,
p. ej.:
    docker run -d --name pgvector-test -e POSTGRES_PASSWORD=test \
        -p 5432:5432 pgvector/pgvector:pg18
    TEST_DATABASE_URL=postgresql://postgres:test@localhost:5432/postgres \
        .venv/Scripts/python -m pytest tests/integration -q
y el extra de ingesta (`pip install '.[ingest]'`) para los embeddings reales.
Sin entorno, se saltan: los unit tests usan almacén falso.
"""

import os

import pytest

from app.core.clientes import AlmacenVectorial, ClienteEmbeddings
from app.rag.retrieval import recuperar

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL no definido (integración con pgvector)",
)

try:
    import sentence_transformers  # noqa: F401

    _ST_OK = True
except ImportError:
    _ST_OK = False

pytestmark = pytest.mark.skipif(
    not _ST_OK, reason="sentence-transformers no instalado (extra [ingest])"
)


@pytest.fixture()
def almacen() -> AlmacenVectorial:
    almacen = AlmacenVectorial(os.environ["TEST_DATABASE_URL"])
    almacen.crear_tabla()
    with almacen._conectar() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE fragmentos")
        conn.commit()
    return almacen


def test_faq_recuperada_con_prioridad(almacen):
    """Tarea 4.1: una consulta con FAQ correspondiente la recupera con prioridad."""
    from app.core.modelos import Fragmento

    embeddings = ClienteEmbeddings()
    faq = Fragmento(
        id="faq-1",
        contenido="Las clases del ciclo 2026-I inician el 13 de abril.",
        tipo="faq",
        url="https://github.com/innovafisi/innovabot/blob/main/backend/data/faqs.md",
        titulo="FAQ — ¿Cuándo inician las clases?",
    )
    noticia = Fragmento(
        id="noticia-1",
        contenido="La FISI organizó un torneo deportivo estudiantil en abril.",
        tipo="noticia",
        url="https://sistemas.unmsm.edu.pe/noticia-deporte",
        titulo="Torneo deportivo FISI",
    )
    for f in (faq, noticia):
        f.embedding = embeddings.embeber([f.contenido])[0]
    almacen.indexar([faq, noticia])

    resultados = recuperar(
        "¿cuándo inician las clases del ciclo?",
        embeddings,
        almacen,
        top_k=2,
        min_similitud=0.0,
    )
    assert resultados, "la búsqueda semántica debe recuperar fragmentos"
    assert resultados[0].id == "faq-1"  # la FAQ va primero (boost de prioridad)
    assert any(f.id == "noticia-1" for f in resultados)


def test_filtrable_por_metadata(almacen):
    """La metadata es filtrable con SQL común (spec knowledge-ingestion)."""
    from app.core.modelos import Fragmento

    embeddings = ClienteEmbeddings()
    faq = Fragmento(
        id="faq-2", contenido="La matrícula virtual se hace en el sistema académico.",
        tipo="faq", url="https://x/faqs", titulo="FAQ matrícula",
    )
    faq.embedding = embeddings.embeber([faq.contenido])[0]
    almacen.indexar([faq])

    with almacen._conectar() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, titulo FROM fragmentos WHERE tipo = 'faq'")
        fila = cur.fetchone()
    assert fila == ("faq-2", "FAQ matrícula")
