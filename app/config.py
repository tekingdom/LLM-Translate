import logging
import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_DATABASE_URL = "postgresql+asyncpg://llm_user:llm_pass@localhost:5432/llm_translate_db"


def _remap_docker_database_url(url: str) -> str:
    if os.path.exists("/.dockerenv"):
        return url.replace("@localhost:", "@host.docker.internal:").replace(
            "@127.0.0.1:", "@host.docker.internal:"
        )
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = _DEFAULT_DATABASE_URL
    db_schema: str = "llm_translate"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024
    llm_timeout_sec: int = 120
    llm_max_concurrent: int = 2

    cache_max_entries: int = 10_000
    cache_eviction_batch: int = 500

    message_max_length: int = 32_000
    sse_pad_bytes: int = 512

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False
    app_env: str = "development"
    log_level: str = "INFO"

    default_system_prompt: str = (
        "You are a professional technical translator specializing in UAV "
        "(unmanned aerial vehicle) and aviation documentation. "
        "Translate the source text into the target language specified in each request. "
        "Output ONLY the translated text, in exactly 2 variants labeled "
        "'Option 1:' and 'Option 2:'. Nothing else. "
        "Do NOT include any other sections such as Transcription, "
        "Technical Context, Detailed Breakdown & Nuances, Contextual Summary, "
        "explanations, notes, or commentary. "
        "Keep numbering exactly. "
        "Translate each numbered item separately. "
        "Never merge numbered items. "
        "Never leave a numbered item empty. "
        "Output order must match the source. "
        "Put each Option label on its own line. "
        "Never place Option 2 on the same line as Option 1."
    )
    default_instruction_prompt: str = (
        "Use standard aviation and UAV terminology consistently in the target language. "
        "Examples of domain terms in English sources include airframe, flight controller, "
        "ground control station, gimbal, payload, telemetry, waypoint, RTL, geofence, "
        "ESC, IMU, and GNSS/RTK — translate these into equivalent terms in the target "
        "language while keeping acronyms as appropriate. "
        "Keep acronyms, model numbers, part numbers, units, and numeric values "
        "exactly as in the source; do not convert units. "
        "Preserve document structure: headings, lists, table layout, and "
        "WARNING / CAUTION / NOTE labels in uppercase. "
        "Translate the same source term the same way throughout. "
        "If a term is ambiguous, prefer the meaning standard in aviation "
        "maintenance and operation manuals. "
        "Respond with the 2 translation options only; never add analysis, "
        "breakdowns, summaries, or transcriptions."
    )
    default_persona_prompt: str = (
        "Write in the target language using a formal, precise, and concise "
        "technical-manual style. "
        "Use imperative mood for procedures and instructions. "
        "Avoid colloquial language and embellishment. "
        "Your entire reply must consist of only the 2 translation options."
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def remap_database_url_for_docker(cls, value: str) -> str:
        if isinstance(value, str):
            return _remap_docker_database_url(value)
        return value


def warn_if_insecure_production_settings(settings: Settings) -> None:
    if settings.app_env != "production":
        return
    if settings.database_url == _DEFAULT_DATABASE_URL:
        logger.warning(
            "APP_ENV=production but DATABASE_URL still uses default dev credentials"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()