from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.translation_cache import TranslationCache

settings = get_settings()


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


async def _evict_if_needed(db: AsyncSession) -> None:
    count_result = await db.execute(select(func.count()).select_from(TranslationCache))
    total = count_result.scalar_one()
    if total <= settings.cache_max_entries:
        return

    overflow = total - settings.cache_max_entries
    batch = min(settings.cache_eviction_batch, overflow)
    if batch <= 0:
        return

    stale_ids = await db.execute(
        select(TranslationCache.id)
        .order_by(TranslationCache.last_used_at.asc())
        .limit(batch)
    )
    ids = list(stale_ids.scalars().all())
    if ids:
        await db.execute(delete(TranslationCache).where(TranslationCache.id.in_(ids)))


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
    await _evict_if_needed(db)
    return entry
