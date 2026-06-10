import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import MessageRole


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    source_lang: str = Field(pattern="^(en|zh|th)$")
    target_lang: str = Field(pattern="^(en|zh|th)$")
    detail_level: str = Field(default="normal", pattern="^(normal|short|detailed)$")


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: MessageRole
    content: str
    source_lang: str
    target_lang: str
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
