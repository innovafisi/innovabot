"""Recuperación semántica en PostgreSQL (pgvector) con boost de FAQs (spec rag-answering)."""

from app.core.clientes import AlmacenVectorial, ClienteEmbeddings
from app.core.modelos import Fragmento

# Boost de prioridad para FAQs (design.md §Ingesta): una FAQ compite con su
# distancia × BOOST_FAQ, así sube en el ranking frente a fragmentos iguales.
BOOST_FAQ = 0.8


def recuperar(
    consulta_reescrita: str,
    cliente_embeddings: ClienteEmbeddings,
    almacen: AlmacenVectorial,
    top_k: int = 5,
    min_similitud: float = 0.55,
) -> list[Fragmento]:
    """Top-k fragmentos relevantes para la consulta reescrita.

    Filtra por similitud mínima: sin fragmentos con relevancia suficiente,
    la respuesta es el mensaje estándar de sin resultados.
    """
    embedding = cliente_embeddings.embeber([consulta_reescrita], es_consulta=True)[0]
    resultados = almacen.buscar(embedding, top_k=top_k, boost_faq=BOOST_FAQ)
    return [fragmento for fragmento, similitud in resultados if similitud >= min_similitud]
