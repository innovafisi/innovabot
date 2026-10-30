"""Indexación: embeddings + upsert en pgvector + invalidación de obsoletos.

Genera los embeddings con `ClienteEmbeddings`, hace upsert por hash con
`AlmacenVectorial.indexar` (contenido idéntico → mismo id → sin duplicados) y
marca obsoletos los fragmentos de cada URL cuyo hash ya no está vigente
(`AlmacenVectorial.marcar_obsoletos`): un documento actualizado reemplaza a
su versión anterior.
"""

import logging
from collections import defaultdict

from app.core.modelos import Fragmento

logger = logging.getLogger("innovabot")


def validar_fragmento(fragmento: Fragmento) -> bool:
    """Un fragmento sin URL, tipo o contenido es inválido y no se indexa (spec)."""
    return bool(fragmento.url.strip() and fragmento.tipo.strip() and fragmento.contenido.strip())


def indexar(
    fragmentos: list[Fragmento],
    cliente_embeddings,
    almacen,
) -> dict:
    """Indexa fragmentos por URL y devuelve un resumen de la ejecución.

    Los fragmentos con metadata incompleta se registran y se excluyen. Por
    cada URL se marcan obsoletos los hashes que ya no están vigentes, de modo
    que una re-ingesta sin cambios no inserta nada y un documento actualizado
    deja obsoleta su versión anterior.
    """
    invalidos = [f.id or f.titulo for f in fragmentos if not validar_fragmento(f)]
    for identificador in invalidos:
        logger.warning("Fragmento inválido (URL/tipo/contenido incompleto): %s", identificador)

    validos = [f for f in fragmentos if validar_fragmento(f)]
    por_url: dict[str, list[Fragmento]] = defaultdict(list)
    for fragmento in validos:
        por_url[fragmento.url].append(fragmento)

    insertados = 0
    for url, fragmentos_url in por_url.items():
        embeddings = cliente_embeddings.embeber([f.contenido for f in fragmentos_url])
        for fragmento, embedding in zip(fragmentos_url, embeddings, strict=True):
            fragmento.embedding = embedding
        insertados += almacen.indexar(fragmentos_url)
        almacen.marcar_obsoletos(url, {f.id for f in fragmentos_url})

    return {"indexados": len(validos), "insertados": insertados, "invalidos": len(invalidos)}
