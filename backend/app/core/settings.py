"""Configuración tipada por variables de entorno.

Regla del repo: los secrets viven SOLO aquí (variables de entorno), nunca en
código ni commits. Ver backend/.env.example para la plantilla.
"""

from functools import lru_cache

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings de InnovaBot. Las obligatorias (sin default) fallan al instanciar."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MaaS: LLM principal vía endpoint compatible con OpenAI (SDK `openai`).
    maas_api_key: str
    maas_base_url: str
    main_llm_model: str = "deepseek-v4.1-flash"

    # Ollama: light LM local (guardián, clasificación, reescritura, validación).
    ollama_base_url: str = "http://localhost:11434"
    light_llm_model: str = "qwen2.5:3b-instruct-q4_K_M"
    # Threads de inferencia. Sin valor, Ollama auto-detecta (correcto en el ECS
    # de 4 vCPU uniformes). En CPUs híbridos de desarrollo (P+E+LPE cores,
    # ej. Intel Core Ultra) el auto-detect patina: los threads caen en cores de
    # baja potencia y cada token espera al más lento (~0.2 tok/s vs ~15).
    # Con num_thread = núm. de P-cores se recupera la velocidad normal.
    ollama_num_threads: int | None = None

    # RDS PostgreSQL con pgvector (almacén vectorial).
    database_url: str

    # Telegram: token del bot (BotFather) y secret del webhook.
    telegram_bot_token: str
    telegram_webhook_secret: str

    # CORS: orígenes permitidos separados por coma (solo el frontend de Vercel).
    cors_origins: str

    # Límites de uso (spec usage-limits; defaults 5/min, 30/hora, 500 chars).
    rate_limit_per_minute: int = 5
    rate_limit_per_hour: int = 30
    max_query_chars: int = 500
    # Límite adicional por IP (harden-llm-security, LLM10): rotar el session ID
    # desde una misma IP no debe dar cupo infinito. Solo aplica a la web.
    rate_limit_ip_per_minute: int = 20

    # LLM principal: acotar consumo por llamada (harden-llm-security, LLM10).
    llm_max_tokens: int = 512
    llm_timeout_seconds: float = 30.0

    # Retrieval: top-k y similitud mínima para considerar un fragmento relevante.
    retrieval_top_k: int = 5
    retrieval_min_similitud: float = 0.55

    # Embeddings: mismo modelo garantizado en ingesta y consulta. La revisión
    # fija (commit de Hugging Face) protege la integridad del modelo
    # (harden-llm-security, LLM03): sin ella, "latest" podría cambiar el
    # espacio vectorial bajo nuestros pies.
    embeddings_model: str = "intfloat/multilingual-e5-small"
    embeddings_revision: str = "614241f622f53c4eeff9890bdc4f31cfecc418b3"

    # Ingesta: hosts extra permitidos para descargar PDFs, separados por coma
    # (además de los dominios oficiales fijos en ingestion/pdfs.py).
    ingesta_hosts_permitidos: str = ""

    # Ingesta: rutas de los archivos de conocimiento curado (relativas a backend/).
    faqs_md: str = "data/faqs.md"
    secciones_portal_yml: str = "data/secciones_portal.yml"

    @property
    def origenes_cors(self) -> list[str]:
        """Orígenes CORS como lista (limpia de espacios y vacíos)."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def hosts_ingesta_extra(self) -> list[str]:
        """Hosts extra de la allowlist de ingesta como lista."""
        return [h.strip() for h in self.ingesta_hosts_permitidos.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    """Instancia única de settings.

    Falla con mensaje claro en español si falta una variable obligatoria,
    en lugar del ValidationError crudo de pydantic.
    """
    try:
        return Settings()
    except ValidationError as exc:
        faltan = ", ".join(
            sorted(str(error["loc"][0]).upper() for error in exc.errors() if error.get("loc"))
        )
        raise RuntimeError(
            f"Faltan variables de entorno obligatorias: {faltan}. "
            "Copia backend/.env.example a backend/.env y complétalas."
        ) from exc
