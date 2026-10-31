"""Clientes de servicios externos.

Toda llamada a una API externa (MaaS, Ollama, RDS, Telegram) vive aquí.
Los módulos `guard/`, `rag/`, `ingestion/` e `interfaces/` usan estas
clases; nunca llaman APIs externas directamente (regla de AGENTS.md).
"""

import json
import logging

import httpx
import psycopg
from openai import OpenAI

from app.core.modelos import Fragmento
from app.core.settings import get_settings

logger = logging.getLogger("innovabot")


class ClienteLightLM:
    """Light LM local vía Ollama (`/api/generate`, `format: json`, temperatura 0).

    Se usa para la llamada combinada guard+clasificación+reescritura y para
    la validación anti-alucinación: prompts cortos, salida JSON fiable.
    """

    def __init__(self, base_url: str | None = None, modelo: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.modelo = modelo or settings.light_llm_model
        self.num_threads = settings.ollama_num_threads

    def completar_json(self, sistema: str, prompt: str, timeout: float = 60.0) -> dict:
        """Una llamada al light LM con salida JSON garantizada por Ollama.

        Lanza ValueError si la respuesta no es JSON parseable.
        """
        opciones: dict = {"temperature": 0}
        if self.num_threads:
            # CPUs híbridos de desarrollo: ver comentario en settings.py.
            opciones["num_thread"] = self.num_threads
        peticion = {
            "model": self.modelo,
            "system": sistema,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": opciones,
        }
        with httpx.Client(timeout=timeout) as cliente:
            respuesta = cliente.post(f"{self.base_url}/api/generate", json=peticion)
            respuesta.raise_for_status()
            texto = respuesta.json()["response"]
        try:
            return json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ValueError(f"El light LM no devolvió JSON válido: {texto!r}") from exc


class ClienteLLMPrincipal:
    """LLM principal vía MaaS, consumido con el SDK `openai` contra su
    endpoint compatible (base_url de MaaS + API key de MaaS)."""

    def __init__(self, temperatura: float = 0.2) -> None:
        settings = get_settings()
        self.modelo = settings.main_llm_model
        self.temperatura = temperatura
        self._cliente = OpenAI(api_key=settings.maas_api_key, base_url=settings.maas_base_url)

    def completar(self, sistema: str, usuario: str) -> str:
        """Genera texto con contexto recuperado; temperatura baja por diseño."""
        respuesta = self._cliente.chat.completions.create(
            model=self.modelo,
            temperature=self.temperatura,
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
        )
        contenido = respuesta.choices[0].message.content
        if contenido is None:
            raise ValueError("El LLM principal devolvió una respuesta vacía")
        return contenido


class ClienteEmbeddings:
    """Embeddings locales con sentence-transformers (multilingual-e5-small).

    Import perezoso: torch/sentence-transformers solo se cargan cuando se
    piden embeddings (ingesta o retrieval), no al arrancar la API.
    Los prefijos `query:`/`passage:` son obligatorios en los modelos e5.
    """

    def __init__(self, modelo: str | None = None) -> None:
        self.nombre_modelo = modelo or get_settings().embeddings_model
        self._modelo = None

    def _cargar(self):
        if self._modelo is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depende del entorno
                raise RuntimeError(
                    "sentence-transformers no está instalado. Instala el extra "
                    "`pip install '.[ingest]'` (ver backend/README.md)."
                ) from exc
            self._modelo = SentenceTransformer(self.nombre_modelo)
        return self._modelo

    def embeber(self, textos: list[str], *, es_consulta: bool = False) -> list[list[float]]:
        """Embebe textos; `es_consulta=True` añade el prefijo `query:` de e5."""
        prefijo = "query: " if es_consulta else "passage: "
        vectores = self._cargar().encode(
            [prefijo + t for t in textos], normalize_embeddings=True
        )
        return [v.tolist() for v in vectores]


class AlmacenVectorial:
    """Almacén vectorial: RDS PostgreSQL con pgvector (tabla `fragmentos`).

    El hash SHA-256 del contenido normalizado es la PK (deduplicación por
    upsert); las versiones obsoletas de un documento se marcan con
    `obsoleto=TRUE` por su URL y el retrieval las excluye.
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or get_settings().database_url

    def _conectar(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url)

    def crear_tabla(self) -> None:
        """Crea extensión, tabla e índice HNSW si no existen (idempotente)."""
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS fragmentos (
                    id TEXT PRIMARY KEY,
                    contenido TEXT NOT NULL,
                    embedding vector(384) NOT NULL,
                    tipo TEXT NOT NULL,
                    url TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    fecha DATE,
                    obsoleto BOOLEAN NOT NULL DEFAULT FALSE,
                    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_fragmentos_embedding
                ON fragmentos USING hnsw (embedding vector_cosine_ops)
                """
            )
            conn.commit()

    def indexar(self, fragmentos: list[Fragmento]) -> int:
        """Upsert de fragmentos por hash; devuelve cuántos se insertaron nuevos."""
        insertados = 0
        with self._conectar() as conn, conn.cursor() as cur:
            for f in fragmentos:
                if f.embedding is None:
                    raise ValueError(f"Fragmento {f.id} sin embedding")
                cur.execute(
                    """
                    INSERT INTO fragmentos (id, contenido, embedding, tipo, url, titulo, fecha)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET obsoleto = FALSE
                    """,
                    (f.id, f.contenido, f.embedding, f.tipo, f.url, f.titulo, f.fecha),
                )
                insertados += cur.rowcount
            conn.commit()
        return insertados

    def marcar_obsoletos(self, url: str, ids_vigentes: set[str]) -> None:
        """Marca obsoletos los fragmentos de `url` cuyo hash ya no está vigente."""
        ids = list(ids_vigentes)
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE fragmentos SET obsoleto = TRUE
                WHERE url = %s AND obsoleto = FALSE
                AND NOT (id = ANY(%s))
                """,
                (url, ids),
            )
            conn.commit()

    def buscar(
        self,
        embedding: list[float],
        top_k: int = 5,
        boost_faq: float = 0.8,
    ) -> list[tuple[Fragmento, float]]:
        """Búsqueda semántica top-k con boost de prioridad para FAQs.

        Devuelve (fragmento, similitud) ordenados por distancia con boost:
        un fragmento `tipo=faq` compite con su distancia × `boost_faq`.
        El embedding viaja en formato texto de pgvector (`[a, b, …]`) con
        cast explícito: psycopg adapta listas a `double precision[]`, y el
        operador `<=>` solo existe para tipo `vector`.
        """
        consulta = json.dumps(embedding)
        with self._conectar() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, contenido, tipo, url, titulo, fecha,
                       1 - (embedding <=> %(q)s::vector) AS similitud
                FROM fragmentos
                WHERE obsoleto = FALSE
                ORDER BY (CASE WHEN tipo = 'faq'
                               THEN (embedding <=> %(q)s::vector) * %(boost)s
                               ELSE (embedding <=> %(q)s::vector) END)
                LIMIT %(k)s
                """,
                {"q": consulta, "boost": boost_faq, "k": top_k},
            )
            filas = cur.fetchall()
        return [
            (
                Fragmento(
                    id=fila[0], contenido=fila[1], tipo=fila[2],
                    url=fila[3], titulo=fila[4], fecha=str(fila[5]) if fila[5] else None,
                ),
                float(fila[6]),
            )
            for fila in filas
        ]


class ClienteTelegram:
    """Bot de Telegram: envío de mensajes vía Bot API (webhook en interfaces/)."""

    API = "https://api.telegram.org"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or get_settings().telegram_bot_token

    def enviar_mensaje(self, chat_id: int, texto: str) -> None:
        """Envía un mensaje de texto plano al chat indicado."""
        url = f"{self.API}/bot{self.token}/sendMessage"
        with httpx.Client(timeout=30.0) as cliente:
            respuesta = cliente.post(url, json={"chat_id": chat_id, "text": texto})
            if respuesta.status_code >= 400:
                logger.error("Telegram respondió %s: %s", respuesta.status_code, respuesta.text)
                respuesta.raise_for_status()
