import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.schemas.message import MessageResponse, TranslateResponse
from app.services import cache as cache_service
from app.services import llm as llm_service
from app.services.prompts import get_composed_system_prompt
from app.services.tokens import calc_tokens_per_sec, count_tokens_async

DETAIL_INSTRUCTIONS: dict[str, str] = {
    "normal": "",
    "short": (
        "IMPORTANT OVERRIDE — translation length: SHORT. "
        "Produce the shortest possible translation that is still fully understandable. "
        "Aggressively strip filler words, repetition, and optional qualifiers; keep only "
        "what is essential to convey the meaning. Each option must be noticeably shorter "
        "than a normal translation. This overrides any earlier style guidance about "
        "completeness or formality."
    ),
    "detailed": (
        "IMPORTANT OVERRIDE — translation length: DETAILED. "
        "Produce an expanded translation that conveys the full meaning thoroughly and "
        "exhaustively: make implied subjects, conditions, and context explicit, and "
        "unpack dense or ambiguous phrasing so nothing is left to inference. Each option "
        "may be considerably longer than the source text. This overrides any earlier "
        "instruction to be concise or brief."
    ),
}

OPTION_LABEL_RE = re.compile(r"(?im)^\s*Option\s+\d+\s*:")
REPETITION_MIN_UNIT_CHARS = 8
REPETITION_MAX_UNIT_CHARS = 240
REPETITION_MIN_REPEATS = 3


def _trim_extra_options(text: str) -> tuple[str, bool]:
    option_labels = list(OPTION_LABEL_RE.finditer(text))
    if len(option_labels) <= 2:
        return text, False

    return text[: option_labels[2].start()].rstrip(), True


def _trim_repetitive_tail(text: str) -> tuple[str, bool]:
    stripped = text.rstrip()
    if len(stripped) < REPETITION_MIN_UNIT_CHARS * REPETITION_MIN_REPEATS:
        return text, False

    max_unit_chars = min(REPETITION_MAX_UNIT_CHARS, len(stripped) // REPETITION_MIN_REPEATS)
    for unit_chars in range(REPETITION_MIN_UNIT_CHARS, max_unit_chars + 1):
        unit = stripped[-unit_chars:]
        if not unit.strip():
            continue

        repeat_count = 1
        cursor = len(stripped) - unit_chars
        while cursor - unit_chars >= 0 and stripped[cursor - unit_chars : cursor] == unit:
            repeat_count += 1
            cursor -= unit_chars

        if repeat_count >= REPETITION_MIN_REPEATS:
            return stripped[: cursor + unit_chars].rstrip(), True

    return text, False


def _trim_unbounded_output(text: str) -> tuple[str, bool]:
    trimmed, was_trimmed = _trim_extra_options(text)
    if was_trimmed:
        return trimmed, True

    return _trim_repetitive_tail(text)


def _apply_detail_level(system_prompt: str, detail_level: str) -> str:
    extra = DETAIL_INSTRUCTIONS.get(detail_level, "")
    if extra:
        return f"{system_prompt}\n\n{extra}"
    return system_prompt


def _build_user_content(content: str, source_lang: str, target_lang: str) -> str:
    return f"Translate from {source_lang} to {target_lang}:\n{content}"


async def _get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation | None:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
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
    detail_level: str = "normal",
) -> Message:
    user_message = Message(
        conversation_id=conversation_id,
        role=MessageRole.user,
        content=content,
        source_lang=source_lang,
        target_lang=target_lang,
        detail_level=detail_level,
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
    detail_level: str,
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
        detail_level=detail_level,
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

    user_message = await _create_user_message(
        db, conversation, conversation_id, content, source_lang, target_lang, detail_level
    )

    translated_text: str = ""
    tokens_in = 0
    tokens_out = 0
    latency_ms = 0
    from_cache = False

    use_cache = detail_level == "normal" and cache_service.involves_chinese(source_lang, target_lang)
    if use_cache:
        cached = await cache_service.lookup(db, content, source_lang, target_lang)
        if cached:
            translated_text, _ = _trim_unbounded_output(cached.translated_text)
            tokens_in = await count_tokens_async(content)
            tokens_out = await count_tokens_async(translated_text)
            from_cache = True

    if not from_cache:
        system_prompt = _apply_detail_level(await get_composed_system_prompt(db), detail_level)
        user_content = _build_user_content(content, source_lang, target_lang)
        start = time.perf_counter()
        llm_result = await llm_service.translate(system_prompt, user_content, source_lang, target_lang)
        latency_ms = int((time.perf_counter() - start) * 1000)
        translated_text, _ = _trim_unbounded_output(llm_result.text)
        tokens_in = llm_result.tokens_in
        tokens_out = await count_tokens_async(translated_text)

        if use_cache:
            await cache_service.store(db, content, source_lang, target_lang, translated_text)

    assistant_message = await _save_assistant_message(
        db, conversation_id, translated_text, source_lang, target_lang, detail_level,
        tokens_in, tokens_out, latency_ms, from_cache,
    )
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return TranslateResponse(user_message=user_message, assistant_message=assistant_message)


async def translate_message_stream(
    conversation_id: uuid.UUID,
    content: str,
    source_lang: str,
    target_lang: str,
    detail_level: str = "normal",
) -> AsyncIterator[dict[str, Any]]:
    async with async_session() as db:
        conversation = await _get_conversation(db, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        user_message = await _create_user_message(
            db, conversation, conversation_id, content, source_lang, target_lang, detail_level
        )
        await db.refresh(user_message)
        user_message_dict = _message_to_dict(user_message)
        await db.commit()

    yield {"type": "user_message", "data": user_message_dict}

    translated_text: str = ""
    tokens_in = 0
    tokens_out = 0
    latency_ms = 0
    from_cache = False
    system_prompt: str | None = None

    use_cache = detail_level == "normal" and cache_service.involves_chinese(source_lang, target_lang)
    async with async_session() as db:
        if use_cache:
            cached = await cache_service.lookup(db, content, source_lang, target_lang)
            if cached:
                await db.commit()
                translated_text, _ = _trim_unbounded_output(cached.translated_text)
                tokens_in = await count_tokens_async(content)
                tokens_out = await count_tokens_async(translated_text)
                from_cache = True
                yield {"type": "token", "data": {"delta": translated_text, "from_cache": True}}

        if not from_cache:
            system_prompt = _apply_detail_level(
                await get_composed_system_prompt(db), detail_level
            )

    if not from_cache:
        user_content = _build_user_content(content, source_lang, target_lang)
        tokens_in = await count_tokens_async(system_prompt + user_content)
        start = time.perf_counter()
        current_text = ""
        sent_len = 0

        async for delta in llm_service.translate_stream(
            system_prompt, user_content, source_lang, target_lang
        ):
            current_text += delta
            display_text, should_stop = _trim_unbounded_output(current_text)

            if len(display_text) > sent_len:
                yield {
                    "type": "token",
                    "data": {"delta": display_text[sent_len:], "from_cache": False},
                }
                sent_len = len(display_text)

            if should_stop:
                current_text = display_text
                break

        latency_ms = int((time.perf_counter() - start) * 1000)
        translated_text, _ = _trim_unbounded_output(current_text.strip())
        if len(translated_text) > sent_len:
            yield {
                "type": "token",
                "data": {"delta": translated_text[sent_len:], "from_cache": False},
            }
        tokens_out = await count_tokens_async(translated_text)

        if use_cache:
            async with async_session() as db:
                await cache_service.store(db, content, source_lang, target_lang, translated_text)
                await db.commit()

    async with async_session() as db:
        assistant_message = await _save_assistant_message(
            db, conversation_id, translated_text, source_lang, target_lang, detail_level,
            tokens_in, tokens_out, latency_ms, from_cache,
        )
        await db.refresh(assistant_message)
        assistant_message_dict = _message_to_dict(assistant_message)
        await db.commit()

    yield {
        "type": "done",
        "data": {
            "user_message": user_message_dict,
            "assistant_message": assistant_message_dict,
        },
    }
