import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.schemas.message import MessageResponse, TranslateResponse
from app.services import cache as cache_service
from app.services import llm as llm_service
from app.services.prompts import get_composed_system_prompt
from app.services.tokens import calc_tokens_per_sec, count_tokens

DETAIL_INSTRUCTIONS: dict[str, str] = {
    "normal": "",
    "short": "Translation style: concise and brief. Omit redundant words where the meaning stays clear.",
    "detailed": (
        "Translation style: detailed and thorough. Preserve nuance, context, "
        "and technical precision."
    ),
}


def _build_user_content(content: str, source_lang: str, target_lang: str, detail_level: str) -> str:
    base = f"Translate from {source_lang} to {target_lang}:\n{content}"
    extra = DETAIL_INSTRUCTIONS.get(detail_level, "")
    if extra:
        return f"{extra}\n\n{base}"
    return base


async def _get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id).options(selectinload(Conversation.messages))
    )
    return result.scalar_one_or_none()


def _message_to_dict(message: Message) -> dict[str, Any]:
    return MessageResponse.model_validate(message).model_dump(mode="json")


async def _create_user_message(
    db: AsyncSession,
    conversation: Conversation,
    conversation_id: uuid.UUID,
    content: str,
    source_lang: str,
    target_lang: str,
) -> Message:
    user_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.user,
        content=content,
        source_lang=source_lang,
        target_lang=target_lang,
    )
    db.add(user_message)
    await db.flush()

    if not conversation.title:
        conversation.title = content[:80] + ("..." if len(content) > 80 else "")

    return user_message


async def _save_assistant_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    translated_text: str,
    source_lang: str,
    target_lang: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    from_cache: bool,
) -> Message:
    tokens_per_sec_in = calc_tokens_per_sec(tokens_in, latency_ms) if not from_cache else 0.0
    tokens_per_sec_out = calc_tokens_per_sec(tokens_out, latency_ms) if not from_cache else 0.0

    assistant_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.assistant,
        content=translated_text,
        source_lang=source_lang,
        target_lang=target_lang,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        tokens_per_sec_in=tokens_per_sec_in,
        tokens_per_sec_out=tokens_per_sec_out,
        from_cache=from_cache,
    )
    db.add(assistant_message)
    await db.flush()
    return assistant_message


async def translate_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    content: str,
    source_lang: str,
    target_lang: str,
    detail_level: str = "normal",
) -> TranslateResponse:
    conversation = await _get_conversation(db, conversation_id)
    if not conversation:
        raise ValueError("Conversation not found")

    user_message = await _create_user_message(db, conversation, conversation_id, content, source_lang, target_lang)

    translated_text: str = ""
    tokens_in = 0
    tokens_out = 0
    latency_ms = 0
    from_cache = False

    use_cache = detail_level == "normal" and cache_service.involves_chinese(source_lang, target_lang)
    if use_cache:
        cached = await cache_service.lookup(db, content, source_lang, target_lang)
        if cached:
            translated_text = cached.translated_text
            tokens_in = count_tokens(content)
            tokens_out = count_tokens(translated_text)
            from_cache = True

    if not from_cache:
        system_prompt = await get_composed_system_prompt(db)
        user_content = _build_user_content(content, source_lang, target_lang, detail_level)
        start = time.perf_counter()
        llm_result = await llm_service.translate(system_prompt, user_content, source_lang, target_lang)
        latency_ms = int((time.perf_counter() - start) * 1000)
        translated_text = llm_result.text
        tokens_in = llm_result.tokens_in
        tokens_out = llm_result.tokens_out

        if use_cache:
            await cache_service.store(db, content, source_lang, target_lang, translated_text)

    assistant_message = await _save_assistant_message(
        db, conversation_id, translated_text, source_lang, target_lang,
        tokens_in, tokens_out, latency_ms, from_cache,
    )
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return TranslateResponse(user_message=user_message, assistant_message=assistant_message)


async def translate_message_stream(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    content: str,
    source_lang: str,
    target_lang: str,
    detail_level: str = "normal",
) -> AsyncIterator[dict[str, Any]]:
    conversation = await _get_conversation(db, conversation_id)
    if not conversation:
        raise ValueError("Conversation not found")

    user_message = await _create_user_message(db, conversation, conversation_id, content, source_lang, target_lang)
    await db.refresh(user_message)
    yield {"type": "user_message", "data": _message_to_dict(user_message)}

    translated_text: str = ""
    tokens_in = 0
    tokens_out = 0
    latency_ms = 0
    from_cache = False

    use_cache = detail_level == "normal" and cache_service.involves_chinese(source_lang, target_lang)
    if use_cache:
        cached = await cache_service.lookup(db, content, source_lang, target_lang)
        if cached:
            translated_text = cached.translated_text
            tokens_in = count_tokens(content)
            tokens_out = count_tokens(translated_text)
            from_cache = True
            yield {"type": "token", "data": {"delta": translated_text, "from_cache": True}}

    if not from_cache:
        system_prompt = await get_composed_system_prompt(db)
        user_content = _build_user_content(content, source_lang, target_lang, detail_level)
        tokens_in = count_tokens(system_prompt + user_content)
        start = time.perf_counter()
        accumulated: list[str] = []

        async for delta in llm_service.translate_stream(system_prompt, user_content, source_lang, target_lang):
            accumulated.append(delta)
            yield {"type": "token", "data": {"delta": delta, "from_cache": False}}

        latency_ms = int((time.perf_counter() - start) * 1000)
        translated_text = "".join(accumulated).strip()
        tokens_out = count_tokens(translated_text)

        if use_cache:
            await cache_service.store(db, content, source_lang, target_lang, translated_text)

    assistant_message = await _save_assistant_message(
        db, conversation_id, translated_text, source_lang, target_lang,
        tokens_in, tokens_out, latency_ms, from_cache,
    )
    await db.refresh(assistant_message)

    yield {
        "type": "done",
        "data": {
            "user_message": _message_to_dict(user_message),
            "assistant_message": _message_to_dict(assistant_message),
        },
    }
