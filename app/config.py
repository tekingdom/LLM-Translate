import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _remap_docker_database_url(url: str) -> str:
    if os.path.exists("/.dockerenv"):
        return url.replace("@localhost:", "@host.docker.internal:").replace(
            "@127.0.0.1:", "@host.docker.internal:"
        )
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://llm_user:llm_pass@localhost:5432/llm_translate_db"
    db_schema: str = "llm_translate"

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    llm_temperature: float = 0.2
    llm_max_tokens: int = 1024
    llm_timeout_sec: int = 120

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    default_system_prompt: str = (
        "You are a professional technical translator specializing in UAV "
        "(unmanned aerial vehicle) and aviation documentation. "
        "Translate Chinese to English. "
        "Output ONLY the translated text, in exactly 2 variants labeled "
        "'Option 1:' and 'Option 2:'. Nothing else. "
        "Do NOT include any other sections such as Transcription, "
        "Technical Context, Detailed Breakdown & Nuances, Contextual Summary, "
        "explanations, notes, or commentary. "
        "Keep numbering exactly. "
        "Translate each numbered item separately. "
        "Never merge numbered items. "
        "Never leave a numbered item empty. "
        "Output order must match the source."
    )
    default_instruction_prompt: str = (
        "Use standard aviation and UAV terminology consistently "
        "(e.g. airframe, flight controller, ground control station, gimbal, "
        "payload, telemetry, waypoint, RTL, geofence, ESC, IMU, GNSS/RTK). "
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
        "Write in a formal, precise, and concise technical-manual style. "
        "Use imperative mood for procedures and instructions "
        "(e.g. 'Check the propeller', not 'You should check the propeller'). "
        "Avoid colloquial language and embellishment. "
        "Your entire reply must consist of only the 2 translation options."
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def remap_database_url_for_docker(cls, value: str) -> str:
        if isinstance(value, str):
            return _remap_docker_database_url(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()