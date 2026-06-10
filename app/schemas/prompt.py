from datetime import datetime

from pydantic import BaseModel, Field

from app.models.prompt import PromptType


class PromptResponse(BaseModel):
    prompt_type: PromptType
    content: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromptUpdate(BaseModel):
    content: str = Field(min_length=1)
