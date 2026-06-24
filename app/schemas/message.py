import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.config import get_settings
from app.models.message import MessageRole

settings = get_settings()


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=settings.message_max_length)
    source_lang: str = Field(pattern="^(en|zh|th)$")
    target_lang: str = Field(pattern="^(en|zh|th)$")
    detail_level: str = Field(default="normal", pattern="^(normal|short|detailed)$")
    num_options: int = Field(default=1, ge=1, le=3)


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    source_lang: str
    target_lang: str
    detail_level: str = "normal"
    tokens_in: int
    tokens_out: int
    latency_ms: int
    tokens_per_sec_in: float
    tokens_per_sec_out: float
    from_cache: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TranslateResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


def validate_message_fields(
    content: str,
    source_lang: str,
    target_lang: str,
    detail_level: str = "normal",
    num_options: int = 1,
) -> None:
    MessageCreate(
        content=content,
        source_lang=source_lang,
        target_lang=target_lang,
        detail_level=detail_level,
        num_options=num_options,
    )
