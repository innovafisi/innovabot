"""Tareas 2.5 y soporte de chunking: hash SHA-256 de contenido normalizado,
deduplicación por upsert e invalidación de versiones obsoletas por URL.

Verificación (tasks.md): una re-ingesta sin cambios no inserta duplicados y
un documento actualizado (contenido cambia → nuevo hash) reemplaza al
anterior (el anterior queda obsoleto por url).
"""

from app.core.modelos import Fragmento
from app.ingestion.chunking import fragmentar, hash_contenido, normalizar
from app.ingestion.indexar import indexar


class EmbeddingsFalsos:
    """Mock de ClienteEmbeddings: vectores deterministas, sin descargar modelos."""

    def embeber(self, textos, *, es_consulta=False):
        return [[float(len(t)), 1.0, 0.0] for t in textos]


class AlmacenFalso:
    """Mock de AlmacenVectorial: upsert por id + obsoletos por url."""

    def __init__(self) -> None:
        self.fragmentos: dict[str, Fragmento] = {}
        self.obsoletos: set[str] = set()

    def indexar(self, fragmentos):
        nuevos = sum(1 for f in fragmentos if f.id not in self.fragmentos)
        for f in fragmentos:
            self.fragmentos[f.id] = f
        return nuevos

    def marcar_obsoletos(self, url, ids_vigentes):
        for id_, f in self.fragmentos.items():
            if f.url == url and id_ not in ids_vigentes:
                self.obsoletos.add(id_)


# ---- chunking: normalización y hash (deduplicación) ----


def test_hash_estable_ante_espacios() -> None:
    """Contenido idéntico con distinto formato de espacios → mismo hash."""
    assert hash_contenido("matrícula 2026-1\n\nen marzo") == hash_contenido(
        "  matrícula 2026-1   en   marzo  "
    )
    assert normalizar(" a\n b  c ") == "a b c"


def test_hash_diferente_ante_contenido_distinto() -> None:
    """Un cambio de contenido cambia el hash (nuevo id)."""
    assert hash_contenido("versión 1") != hash_contenido("versión 2")


def test_fragmentar_genera_un_fragmento_por_seccion() -> None:
    """Las secciones del documento viajan en fragmentos separados."""
    texto = (
        "SECCION 1: INFORMACION GENERAL\nTexto de la primera sección.\n\n"
        "SECCION 2: REQUISITOS\nTexto de la segunda sección."
    )
    fragmentos = fragmentar(texto, tipo="pdf", url="https://x/doc.pdf", titulo="Doc")

    assert len(fragmentos) == 2
    assert fragmentos[0].id != fragmentos[1].id
    assert "SECCION 1" in fragmentos[0].contenido
    assert "SECCION 2" in fragmentos[1].contenido


def test_seccion_larga_se_divide_con_solapamiento() -> None:
    """Una sección más larga que la ventana genera ventanas solapadas."""
    cuerpo = "palabra " * 400  # ~3200 caracteres en una sola sección
    texto = f"SECCION LARGA\n{cuerpo}"
    fragmentos = fragmentar(texto, tipo="pdf", url="https://x/largo.pdf", titulo="Largo")

    assert len(fragmentos) > 1
    # solapamiento: la ventana 2 arranca dentro del texto que ya cubría la ventana 1
    cuerpo_1 = fragmentos[0].contenido.split("\n\n")[-1]
    cuerpo_2 = fragmentos[1].contenido.split("\n\n")[-1]
    assert cuerpo_2[:100] in cuerpo_1


# ---- indexar: deduplicación e invalidación (tarea 2.5) ----


def test_reingesta_sin_cambios_no_inserta_duplicados() -> None:
    """Re-indexar el mismo contenido no inserta nada nuevo ni invalida nada."""
    fragmentos = fragmentar(
        "Comunicado de matrícula: las fechas son en marzo.",
        tipo="noticia",
        url="https://x/noticia-1",
        titulo="Comunicado",
    )
    almacen = AlmacenFalso()

    primera = indexar(fragmentos, EmbeddingsFalsos(), almacen)
    assert primera["insertados"] == len(fragmentos)

    segunda = indexar(fragmentos, EmbeddingsFalsos(), almacen)
    assert segunda["insertados"] == 0  # mismo hash → upsert, sin duplicados
    assert almacen.obsoletos == set()
    assert len(almacen.fragmentos) == len(fragmentos)


def test_documento_actualizado_reemplaza_al_anterior() -> None:
    """Contenido cambiado → nuevo hash; el fragmento anterior queda obsoleto por url."""
    url = "https://x/noticia-1"
    almacen = AlmacenFalso()

    viejos = fragmentar(
        "Comunicado: matrícula ordinaria en marzo.",
        tipo="noticia", url=url, titulo="Comunicado",
    )
    indexar(viejos, EmbeddingsFalsos(), almacen)

    nuevos = fragmentar(
        "Comunicado actualizado: matrícula ordinaria en abril.",
        tipo="noticia", url=url, titulo="Comunicado",
    )
    resumen = indexar(nuevos, EmbeddingsFalsos(), almacen)

    assert resumen["insertados"] == len(nuevos)
    assert {f.id for f in viejos} <= almacen.obsoletos  # la versión vieja, obsoleta
    assert not ({f.id for f in nuevos} & almacen.obsoletos)  # la nueva, vigente


def test_fragmento_con_metadata_incompleta_no_se_indexa() -> None:
    """Sin URL o tipo el fragmento es inválido: se registra y se excluye (spec)."""
    invalido = Fragmento(id="x", contenido="sin url", tipo="noticia", url="", titulo="X")
    valido = Fragmento(
        id=hash_contenido("con url"), contenido="con url", tipo="noticia",
        url="https://x/1", titulo="Válido",
    )
    almacen = AlmacenFalso()

    resumen = indexar([invalido, valido], EmbeddingsFalsos(), almacen)

    assert resumen["invalidos"] == 1
    assert resumen["indexados"] == 1
    assert set(almacen.fragmentos) == {valido.id}


def test_indexar_asigna_embeddings_a_los_fragmentos() -> None:
    """Cada fragmento indexado queda con su embedding (dimensiones del mock)."""
    fragmentos = fragmentar(
        "Texto breve.", tipo="portal", url="https://x/p", titulo="Portal"
    )
    almacen = AlmacenFalso()
    indexar(fragmentos, EmbeddingsFalsos(), almacen)

    assert all(f.embedding is not None for f in fragmentos)
    assert all(len(f.embedding) == 3 for f in fragmentos)
