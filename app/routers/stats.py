from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.message import Message, MessageRole
from app.models.translation_cache import TranslationCache
from app.schemas.stats import StatsResponse

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    stats_row = await db.execute(
        select(
            func.count(Message.id),
            func.coalesce(func.sum(Message.tokens_in), 0),
            func.coalesce(func.sum(Message.tokens_out), 0),
        ).where(Message.role == MessageRole.assistant)
    )
    total_messages, total_tokens_in, total_tokens_out = stats_row.one()

    cache_hits_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.role == MessageRole.assistant,
            Message.from_cache.is_(True),
        )
    )
    cache_hits = cache_hits_result.scalar() or 0

    cache_total_result = await db.execute(select(func.count(TranslationCache.id)))
    cache_total = cache_total_result.scalar() or 0

    hit_rate = (cache_hits / total_messages * 100) if total_messages > 0 else 0.0

    return StatsResponse(
        total_messages=total_messages,
        total_tokens_in=int(total_tokens_in),
        total_tokens_out=int(total_tokens_out),
        cache_hits=cache_hits,
        cache_total=cache_total,
        cache_hit_rate=round(hit_rate, 2),
    )
