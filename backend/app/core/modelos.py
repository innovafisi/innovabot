"""Modelos de datos compartidos del dominio (sin lógica de negocio)."""

from dataclasses import dataclass, field


@dataclass
class Fragmento:
    """Fragmento de conocimiento indexado en pgvector.

    `id` es el hash SHA-256 del contenido normalizado (deduplicación):
    contenido idéntico → mismo id → upsert sin duplicados.
    """

    id: str
    contenido: str
    tipo: str  # noticia | pdf | faq | portal
    url: str
    titulo: str
    fecha: str | None = None  # ISO YYYY-MM-DD; en portal central, fecha de consulta
    embedding: list[float] | None = None


@dataclass
class Cita:
    """Referencia a la fuente usada en una respuesta."""

    titulo: str
    url: str


@dataclass
class Respuesta:
    """Salida del pipeline de respuesta para ambas interfaces.

    Estados (specs web-ui/rag-answering): ok | bloqueada | sin_resultados | limitada.
    """

    reply: str
    citas: list[Cita] = field(default_factory=list)
    estado: str = "ok"


@dataclass
class ResultadoGuardia:
    """Salida de la llamada combinada del light LM: guard + clasificación + reescritura."""

    safe: bool
    categoria: str  # académico | admisión | trámites | noticias | general | fuera_de_alcance
    consulta_reescrita: str
