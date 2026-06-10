from collections.abc import AsyncIterator
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import get_settings
from app.services.tokens import count_tokens

settings = get_settings()


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "not-needed",
        timeout=settings.llm_timeout_sec,
    )


def _build_messages(system_prompt: str, user_content: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


async def translate(
    system_prompt: str,
    user_content: str,
    source_lang: str,
    target_lang: str,
) -> LLMResult:
    client = _get_client()
    messages = _build_messages(system_prompt, user_content)

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )

    text = (response.choices[0].message.content or "").strip()

    usage = response.usage
    if usage and usage.prompt_tokens is not None and usage.completion_tokens is not None:
        tokens_in = usage.prompt_tokens
        tokens_out = usage.completion_tokens
    else:
        tokens_in = count_tokens(system_prompt + user_content)
        tokens_out = count_tokens(text)

    return LLMResult(text=text, tokens_in=tokens_in, tokens_out=tokens_out)


async def translate_stream(
    system_prompt: str,
    user_content: str,
    source_lang: str,
    target_lang: str,
) -> AsyncIterator[str]:
    client = _get_client()
    messages = _build_messages(system_prompt, user_content)

    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
