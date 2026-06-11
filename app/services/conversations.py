import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.models.conversation import Conversation
from app.models.message import Message

CHAT_MESSAGE_LIMIT = 50


async def load_conversation_with_recent_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    message_limit: int = CHAT_MESSAGE_LIMIT,
) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        return None

    msg_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(message_limit)
    )
    messages = list(reversed(msg_result.scalars().all()))
    attributes.set_committed_value(conversation, "messages", messages)
    return conversation
