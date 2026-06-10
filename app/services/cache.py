from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.translation_cache import TranslationCache


def involves_chinese(source_lang: str, target_lang: str) -> bool:
    return source_lang == "zh" or target_lang == "zh"


async def lookup(
    db: AsyncSession,
    source_text: str,
    source_lang: str,
    target_lang: str,
) -> TranslationCache | None:
    result = await db.execute(
        select(TranslationCache).where(
            TranslationCache.source_text == source_text,
            TranslationCache.source_lang == source_lang,
            TranslationCache.target_lang == target_lang,
        )
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.hit_count += 1
        entry.last_used_at = datetime.now(timezone.utc)
        await db.flush()
    return entry


async def store(
    db: AsyncSession,
    source_text: str,
    source_lang: str,
    target_lang: str,
    translated_text: str,
) -> TranslationCache:
    result = await db.execute(
        select(TranslationCache).where(
            TranslationCache.source_text == source_text,
            TranslationCache.source_lang == source_lang,
            TranslationCache.target_lang == target_lang,
        )
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.translated_text = translated_text
        entry.last_used_at = datetime.now(timezone.utc)
    else:
        entry = TranslationCache(
            source_text=source_text,
            source_lang=source_lang,
            target_lang=target_lang,
            translated_text=translated_text,
        )
        db.add(entry)
    await db.flush()
    return entry
