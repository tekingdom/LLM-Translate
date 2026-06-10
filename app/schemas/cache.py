import uuid
from datetime import datetime

from pydantic import BaseModel


class CacheEntryResponse(BaseModel):
    id: uuid.UUID
    source_text: str
    source_lang: str
    target_lang: str
    translated_text: str
    hit_count: int
    created_at: datetime
    last_used_at: datetime

    model_config = {"from_attributes": True}
