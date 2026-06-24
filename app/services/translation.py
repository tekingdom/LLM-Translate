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

OPTION_LABEL_RE = re.compile(r"(?im)(?:^|\s)(Option\s+\d+\s*:)")
REPETITION_MIN_UNIT_CHARS = 8
REPETITION_MAX_UNIT_CHARS = 240
REPETITION_MIN_REPEATS = 3


def _trim_extra_options(text: str, max_options: int = 2) -> tuple[str, bool]:
    option_labels = list(OPTION_LABEL_RE.finditer(text))
    if max_options == 1:
        if not option_labels:
            return text, False
        return text[: option_labels[0].start(1)].rstrip(), True
    if len(option_labels) <= max_options:
        return text, False

    return text[: option_labels[max_options].start(1)].rstrip(), True


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


def _trim_unbounded_output(text: str, max_options: int = 2) -> tuple[str, bool]:
    trimmed, was_trimmed = _trim_extra_options(text, max_options)
    if was_trimmed:
        return trimmed, True

    option_count = len(list(OPTION_LABEL_RE.finditer(text)))
    if max_options > 1 and option_count < max_options:
        return text, False

    return _trim_repetitive_tail(text)


LANG_NAMES: dict[str, str] = {
    "en": "English",
    "zh": "中文 (Chinese)",
    "th": "ภาษาไทย (Thai)",
}


def _lang_name(lang: str) -> str:
    return LANG_NAMES.get(lang, lang)


TARGET_LANG_EXTRA: dict[str, str] = {
    "th": (
        "All translation options MUST use Thai script (อักษรไทย). "
        "Do NOT output English or romanization."
    ),
}


_FIXED_OPTION_COUNT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"exactly 2 variants", re.IGNORECASE), "translation variants"),
    (re.compile(r"'Option 1:' and 'Option 2:'", re.IGNORECASE), "labeled translation variants"),
    (re.compile(r"only the 2 translation options", re.IGNORECASE), "only the translation options"),
    (re.compile(r"the 2 translation options only", re.IGNORECASE), "the translation options only"),
    (re.compile(r"the 2 translation options", re.IGNORECASE), "the translation options"),
    (re.compile(r"Never place Option 2 on the same line as Option 1\.", re.IGNORECASE), ""),
)


def _neutralize_fixed_option_count(prompt: str) -> str:
    result = prompt
    for pattern, replacement in _FIXED_OPTION_COUNT_REPLACEMENTS:
        result = pattern.sub(replacement, result)
    return result


def _option_labels_range(num_options: int) -> str:
    if num_options <= 1:
        return ""
    if num_options == 2:
        return "Option 1 and Option 2"
    return f"Option 1 through Option {num_options}"


def _apply_num_options(system_prompt: str, num_options: int) -> str:
    if num_options == 1:
        directive = (
            "IMPORTANT OVERRIDE — output format: SINGLE translation. "
            "Output ONLY the translated text with no variants, no labels, "
            "and no 'Option N:' prefixes. Nothing else."
        )
    elif num_options == 2:
        directive = (
            "IMPORTANT OVERRIDE — output format: exactly 2 variants labeled "
            "'Option 1:' and 'Option 2:'. Put each Option label on its own line. "
            "Output ONLY these 2 translation options; no analysis or commentary."
        )
    else:
        directive = (
            "CRITICAL FINAL OVERRIDE — ignore every earlier instruction that limits "
            "output to 2 options, 2 variants, or only Option 1 and Option 2. "
            "Output format: exactly 3 variants labeled 'Option 1:', 'Option 2:', "
            "and 'Option 3:'. You MUST include all three options. Put each Option "
            "label on its own line. Output ONLY these 3 translation options; "
            "no analysis or commentary."
        )
    return f"{system_prompt}\n\n{directive}"


def _apply_detail_level(system_prompt: str, detail_level: str) -> str:
    extra = DETAIL_INSTRUCTIONS.get(detail_level, "")
    if extra:
        return f"{system_prompt}\n\n{extra}"
    return system_prompt


def _apply_language_direction(
    system_prompt: str, source_lang: str, target_lang: str, num_options: int
) -> str:
    source_name = _lang_name(source_lang)
    target_name = _lang_name(target_lang)
    if num_options <= 1:
        lang_clause = f"The translation must be written entirely in {target_name}."
    else:
        options_ref = _option_labels_range(num_options)
        lang_clause = (
            f"{options_ref} must be written entirely in {target_name}."
        )
    directive = (
        f"IMPORTANT OVERRIDE — translation direction: translate from {source_name} "
        f"to {target_name}. {lang_clause} This overrides any earlier instruction "
        "about source or target language."
    )
    extra = TARGET_LANG_EXTRA.get(target_lang, "")
    if extra and num_options > 1:
        directive = f"{directive} {extra}"
    elif extra and num_options <= 1:
        directive = (
            f"{directive} The translation MUST use Thai script (อักษรไทย). "
            "Do NOT output English or romanization."
        )
    return f"{system_prompt}\n\n{directive}"


def _build_system_prompt(
    base_prompt: str,
    source_lang: str,
    target_lang: str,
    detail_level: str,
    num_options: int,
) -> str:
    prompt = base_prompt
    if num_options != 2:
        prompt = _neutralize_fixed_option_count(prompt)
    prompt = _apply_language_direction(prompt, source_lang, target_lang, num_options)
    prompt = _apply_detail_level(prompt, detail_level)
    return _apply_num_options(prompt, num_options)


def _build_user_content(content: str, source_lang: str, target_lang: str) -> str:
    if target_lang == "th":
        return f"แปลจาก{_lang_name(source_lang)}เป็นภาษาไทย:\n{content}"
    return f"Translate from {_lang_name(source_lang)} to {_lang_name(target_lang)}:\n{content}"


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
    num_options: int = 1,
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

    use_cache = (
        detail_level == "normal"
        and num_options == 2
        and cache_service.involves_chinese(source_lang, target_lang)
    )
    if use_cache:
        cached = await cache_service.lookup(db, content, source_lang, target_lang)
        if cached:
            translated_text, _ = _trim_unbounded_output(cached.translated_text, num_options)
            tokens_in = await count_tokens_async(content)
            tokens_out = await count_tokens_async(translated_text)
            from_cache = True

    if not from_cache:
        system_prompt = _build_system_prompt(
            await get_composed_system_prompt(db),
            source_lang,
            target_lang,
            detail_level,
            num_options,
        )
        user_content = _build_user_content(content, source_lang, target_lang)
        start = time.perf_counter()
        llm_result = await llm_service.translate(system_prompt, user_content, source_lang, target_lang)
        latency_ms = int((time.perf_counter() - start) * 1000)
        translated_text, _ = _trim_unbounded_output(llm_result.text, num_options)
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
    num_options: int = 1,
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

    use_cache = (
        detail_level == "normal"
        and num_options == 2
        and cache_service.involves_chinese(source_lang, target_lang)
    )
    async with async_session() as db:
        if use_cache:
            cached = await cache_service.lookup(db, content, source_lang, target_lang)
            if cached:
                await db.commit()
                translated_text, _ = _trim_unbounded_output(cached.translated_text, num_options)
                tokens_in = await count_tokens_async(content)
                tokens_out = await count_tokens_async(translated_text)
                from_cache = True
                yield {"type": "token", "data": {"delta": translated_text, "from_cache": True}}

        if not from_cache:
            system_prompt = _build_system_prompt(
                await get_composed_system_prompt(db),
                source_lang,
                target_lang,
                detail_level,
                num_options,
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
            display_text, should_stop = _trim_unbounded_output(current_text, num_options)

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
        translated_text, _ = _trim_unbounded_output(current_text.strip(), num_options)
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
