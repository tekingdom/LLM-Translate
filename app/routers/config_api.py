from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.app_config import AppConfig
from app.schemas.app_config import AppConfigResponse, AppConfigUpdate

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=list[AppConfigResponse])
async def list_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).order_by(AppConfig.key))
    return result.scalars().all()


@router.get("/{key}", response_model=AppConfigResponse)
async def get_config(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Config key not found")
    return entry


@router.put("/{key}", response_model=AppConfigResponse)
async def upsert_config(key: str, body: AppConfigUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = body.value
    else:
        entry = AppConfig(key=key, value=body.value)
        db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry


@router.delete("/{key}", status_code=204)
async def delete_config(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Config key not found")
    await db.delete(entry)
