"""Tarea 2.3: carga de FAQs curadas desde el Markdown del repo.

Verificación (tasks.md): cada Q&A genera un fragmento con metadata
`tipo=faq` y re-ejecutar no duplica entradas (mismo hash → mismo id).
"""

from app.ingestion.faqs import URL_FAQS, cargar_faqs, parsear_faqs

FAQS_MD = """# Preguntas frecuentes sobre la FISI

## ¿Cómo ingreso a la FISI?

Mediante el examen de admisión de la UNMSM. Revisa el portal de la OCA.

## ¿Cómo realizo mi matrícula?

A través del SUM dentro del calendario académico.

## ¿Pregunta sin respuesta?
"""


def test_cada_qa_genera_fragmento_con_tipo_faq(tmp_path) -> None:
    """Un fragmento por Q&A, con tipo=faq, la pregunta como título y URL fija."""
    ruta = tmp_path / "faqs.md"
    ruta.write_text(FAQS_MD, encoding="utf-8")

    fragmentos = cargar_faqs(ruta)

    assert len(fragmentos) == 2  # el Q&A sin respuesta se descarta
    assert all(f.tipo == "faq" for f in fragmentos)
    assert all(f.url == URL_FAQS for f in fragmentos)
    assert fragmentos[0].titulo == "¿Cómo ingreso a la FISI?"
    assert "examen de admisión" in fragmentos[0].contenido
    assert fragmentos[0].contenido.startswith("¿Cómo ingreso a la FISI?")


def test_reejecutar_no_duplica_mismo_hash_mismo_id(tmp_path) -> None:
    """Re-ejecutar la carga produce los mismos ids (hash): sin duplicados."""
    ruta = tmp_path / "faqs.md"
    ruta.write_text(FAQS_MD, encoding="utf-8")

    primera = cargar_faqs(ruta)
    segunda = cargar_faqs(ruta)

    assert [f.id for f in primera] == [f.id for f in segunda]
    assert len({f.id for f in primera + segunda}) == len(primera)


def test_cambio_de_respuesta_cambia_el_id(tmp_path) -> None:
    """Modificar una respuesta cambia el hash: la versión nueva reemplaza a la vieja."""
    ruta = tmp_path / "faqs.md"
    ruta.write_text(FAQS_MD, encoding="utf-8")
    original = cargar_faqs(ruta)

    ruta.write_text(
        FAQS_MD.replace(
            "Mediante el examen de admisión de la UNMSM.",
            "Mediante el examen de admisión o modalidades.",
        ),
        encoding="utf-8",
    )
    actualizada = cargar_faqs(ruta)

    assert actualizada[0].id != original[0].id
    assert actualizada[1].id == original[1].id  # la FAQ intacta conserva su id


def test_parsear_faqs_ignora_titulo_de_nivel_1() -> None:
    """El encabezado `# ` del archivo no genera Q&A."""
    pares = parsear_faqs(FAQS_MD)
    preguntas = [pregunta for pregunta, _ in pares]
    assert preguntas == ["¿Cómo ingreso a la FISI?", "¿Cómo realizo mi matrícula?"]


def test_faqs_reales_del_repo_cargan() -> None:
    """El archivo real backend/data/faqs.md carga íntegro como FAQs."""
    fragmentos = cargar_faqs("data/faqs.md")

    assert 6 <= len(fragmentos) <= 10
    assert all(f.tipo == "faq" for f in fragmentos)
    assert len({f.id for f in fragmentos}) == len(fragmentos)
