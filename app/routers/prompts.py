from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prompt import Prompt, PromptType
from app.schemas.prompt import PromptResponse, PromptUpdate
from app.services.prompts import DEFAULTS, invalidate_prompt_cache

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptResponse])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prompt).order_by(Prompt.prompt_type))
    prompts = {p.prompt_type: p for p in result.scalars().all()}
    responses = []
    for prompt_type in PromptType:
        if prompt_type in prompts:
            responses.append(PromptResponse.model_validate(prompts[prompt_type]))
        else:
            responses.append(
                PromptResponse(
                    prompt_type=prompt_type,
                    content=DEFAULTS[prompt_type],
                    updated_at=datetime.now(timezone.utc),
                )
            )
    return responses


@router.put("/{prompt_type}", response_model=PromptResponse)
async def update_prompt(
    prompt_type: PromptType,
    body: PromptUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Prompt).where(Prompt.prompt_type == prompt_type))
    prompt = result.scalar_one_or_none()
    if prompt:
        prompt.content = body.content
    else:
        prompt = Prompt(prompt_type=prompt_type, content=body.content)
        db.add(prompt)
    await db.flush()
    await db.refresh(prompt)
    invalidate_prompt_cache()
    return prompt
