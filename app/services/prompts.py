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


async def get_prompt(db: AsyncSession, prompt_type: PromptType) -> str:
    result = await db.execute(select(Prompt).where(Prompt.prompt_type == prompt_type))
    prompt = result.scalar_one_or_none()
    if prompt:
        return prompt.content
    return DEFAULTS[prompt_type]


async def get_composed_system_prompt(db: AsyncSession) -> str:
    system = await get_prompt(db, PromptType.system)
    instruction = await get_prompt(db, PromptType.instruction)
    persona = await get_prompt(db, PromptType.persona)
    return f"{system}\n\n{instruction}\n\n{persona}"


async def seed_default_prompts(db: AsyncSession) -> None:
    for prompt_type, content in DEFAULTS.items():
        result = await db.execute(select(Prompt).where(Prompt.prompt_type == prompt_type))
        if result.scalar_one_or_none() is None:
            db.add(Prompt(prompt_type=prompt_type, content=content))
    await db.flush()
