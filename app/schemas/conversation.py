import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.message import MessageResponse

SUPPORTED_LANGS = ("en", "zh", "th")


class ConversationCreate(BaseModel):
    title: str | None = None
    default_source_lang: str = Field(default="zh", pattern="^(en|zh|th)$")
    default_target_lang: str = Field(default="en", pattern="^(en|zh|th)$")


class ConversationUpdate(BaseModel):
    title: str | None = None
    default_source_lang: str | None = Field(default=None, pattern="^(en|zh|th)$")
    default_target_lang: str | None = Field(default=None, pattern="^(en|zh|th)$")


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str | None
    default_source_lang: str
    default_target_lang: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationWithMessages(ConversationResponse):
    messages: list[MessageResponse] = []
