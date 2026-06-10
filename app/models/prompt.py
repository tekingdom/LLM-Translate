import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PromptType(str, enum.Enum):
    system = "system"
    instruction = "instruction"
    persona = "persona"


class Prompt(Base):
    __tablename__ = "prompts"
    __table_args__ = {"schema": "llm_translate"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_type: Mapped[PromptType] = mapped_column(
        Enum(PromptType, name="prompt_type", native_enum=False), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
