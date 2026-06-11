from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.prompt import Prompt, PromptType

settings = get_settings()

DEFAULTS: dict[PromptType, str] = {
    PromptType.system: settings.default_system_prompt,
    PromptType.instruction: settings.default_instruction_prompt,
    PromptType.persona: settings.default_persona_prompt,
}

_composed_cache: str | None = None


def invalidate_prompt_cache() -> None:
    global _composed_cache
    _composed_cache = None


async def _load_prompts(db: AsyncSession) -> dict[PromptType, str]:
    result = await db.execute(
        select(Prompt).where(Prompt.prompt_type.in_(list(PromptType)))
    )
    stored = {p.prompt_type: p.content for p in result.scalars().all()}
    return {pt: stored.get(pt, DEFAULTS[pt]) for pt in PromptType}


async def get_prompt(db: AsyncSession, prompt_type: PromptType) -> str:
    prompts = await _load_prompts(db)
    return prompts[prompt_type]


async def get_composed_system_prompt(db: AsyncSession) -> str:
    global _composed_cache
    if _composed_cache is not None:
        return _composed_cache

    prompts = await _load_prompts(db)
    _composed_cache = (
        f"{prompts[PromptType.system]}\n\n"
        f"{prompts[PromptType.instruction]}\n\n"
        f"{prompts[PromptType.persona]}"
    )
    return _composed_cache


async def warm_prompt_cache(db: AsyncSession) -> None:
    await get_composed_system_prompt(db)


async def seed_default_prompts(db: AsyncSession) -> None:
    for prompt_type, content in DEFAULTS.items():
        result = await db.execute(select(Prompt).where(Prompt.prompt_type == prompt_type))
        if result.scalar_one_or_none() is None:
            db.add(Prompt(prompt_type=prompt_type, content=content))
    await db.flush()
    invalidate_prompt_cache()
