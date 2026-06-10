import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.translation_cache import TranslationCache
from app.schemas.cache import CacheEntryResponse

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("", response_model=list[CacheEntryResponse])
async def list_cache(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TranslationCache).order_by(TranslationCache.last_used_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.delete("/{cache_id}", status_code=204)
async def delete_cache_entry(cache_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TranslationCache).where(TranslationCache.id == cache_id))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    await db.delete(entry)
