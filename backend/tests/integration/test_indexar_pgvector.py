"""Tarea 2.6 (INTEGRACIÓN): indexación real con embeddings + pgvector.

Este test se salta limpiamente si no está configurada la base de datos de
prueba. Cómo correrlo con un pgvector local:

    docker run -d --name pgvector-test \
        -e POSTGRES_PASSWORD=test -p 5432:5432 pgvector/pgvector:pg18

    # desde backend/ (Windows PowerShell):
    $env:TEST_DATABASE_URL = "postgresql://postgres:test@localhost:5432/postgres"
    .venv/Scripts/python -m pytest tests/integration -q

Requiere además sentence-transformers (los embeddings son reales, no mock):

    pip install '.[ingest]'

Verificación (tasks.md): un fragmento indexado es recuperable por búsqueda
semántica y filtrable por metadata (tipo, url, titulo, fecha).
"""

import os
from datetime import date

import psycopg
import pytest

from app.core.clientes import AlmacenVectorial, ClienteEmbeddings
from app.core.modelos import Fragmento
from app.ingestion.chunking import hash_contenido
from app.ingestion.faqs import URL_FAQS
from app.ingestion.indexar import indexar

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason=(
        "requiere TEST_DATABASE_URL apuntando a un PostgreSQL con pgvector "
        "(ej.: docker run -e POSTGRES_PASSWORD=test -p 5432:5432 pgvector/pgvector:pg18)"
    ),
)


def _fragmento(contenido: str, tipo: str, url: str, titulo: str) -> Fragmento:
    return Fragmento(
        id=hash_contenido(contenido), contenido=contenido, tipo=tipo,
        url=url, titulo=titulo, fecha="2026-10-30",
    )


def test_indexar_y_recuperar_semanticamente_con_filtro_de_metadata() -> None:
    """Indexa 3 fragmentos reales y los recupera por similitud y por metadata."""
    pytest.importorskip(
        "sentence_transformers",
        reason="requiere sentence-transformers: pip install '.[ingest]'",
    )
    almacen = AlmacenVectorial(database_url=TEST_DATABASE_URL)
    almacen.crear_tabla()

    fragmentos = [
        _fragmento(
            "¿Cómo ingreso a la FISI? Mediante el examen de admisión de la UNMSM "
            "o las modalidades de ingreso que publica la Oficina Central de Admisión.",
            tipo="faq", url=URL_FAQS, titulo="¿Cómo ingreso a la FISI?",
        ),
        _fragmento(
            "La matrícula se realiza a través del Sistema Único de Matrícula dentro "
            "del calendario académico de cada semestre.",
            tipo="noticia", url="https://sistemas.unmsm.edu.pe/site/noticias/1",
            titulo="Comunicado de matrícula",
        ),
        _fragmento(
            "La Universidad Nacional Mayor de San Marcos ofrece servicios de bienestar: "
            "comedores, residencias y atención de salud.",
            tipo="portal", url="https://www.unmsm.edu.pe/comunidad/vida-universitaria",
            titulo="Vida universitaria",
        ),
    ]

    resumen = indexar(fragmentos, ClienteEmbeddings(), almacen)
    assert resumen["indexados"] == 3
    assert resumen["invalidos"] == 0

    # Búsqueda semántica: la consulta sobre admisión recupera la FAQ (con boost).
    cliente = ClienteEmbeddings()
    embedding = cliente.embeber(["¿Cómo ingreso a la facultad?"], es_consulta=True)[0]
    resultados = almacen.buscar(embedding, top_k=3)
    assert resultados, "la búsqueda semántica no devolvió resultados"
    tipos = [fragmento.tipo for fragmento, _ in resultados]
    assert "faq" in tipos

    # Filtrado por metadata: la tabla guarda tipo/url/titulo/fecha consultables por SQL.
    with psycopg.connect(TEST_DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT titulo, url, fecha FROM fragmentos "
            "WHERE tipo = %s AND obsoleto = FALSE ORDER BY titulo",
            ("faq",),
        )
        filas = cur.fetchall()
    assert filas == [("¿Cómo ingreso a la FISI?", URL_FAQS, date(2026, 10, 30))]

    # Limpieza: el índice de prueba queda vacío para la siguiente ejecución.
    with psycopg.connect(TEST_DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM fragmentos")
        conn.commit()
