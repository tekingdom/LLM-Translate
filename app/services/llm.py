import asyncio

from collections.abc import AsyncIterator

from dataclasses import dataclass



from openai import AsyncOpenAI



from app.config import get_settings

from app.services.tokens import count_tokens



settings = get_settings()



_client: AsyncOpenAI | None = None

_semaphore: asyncio.Semaphore | None = None





def _get_client() -> AsyncOpenAI:

    global _client

    if _client is None:

        _client = AsyncOpenAI(

            base_url=settings.llm_base_url,

            api_key=settings.llm_api_key or "not-needed",

            timeout=settings.llm_timeout_sec,

        )

    return _client





def _get_semaphore() -> asyncio.Semaphore:

    global _semaphore

    if _semaphore is None:

        _semaphore = asyncio.Semaphore(settings.llm_max_concurrent)

    return _semaphore





@dataclass

class LLMResult:

    text: str

    tokens_in: int

    tokens_out: int





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



    async with _get_semaphore():

        async with asyncio.timeout(settings.llm_timeout_sec):

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





def _chunk_text(chunk) -> str | None:
    if not chunk.choices:
        return None
    choice = chunk.choices[0]
    delta = choice.delta
    if delta and delta.content:
        return delta.content
    # Non-stream final chunks from some providers; streaming Choice has no .message
    message = getattr(choice, "message", None)
    if message and message.content:
        return message.content
    return None





async def translate_stream(

    system_prompt: str,

    user_content: str,

    source_lang: str,

    target_lang: str,

) -> AsyncIterator[str]:

    client = _get_client()

    messages = _build_messages(system_prompt, user_content)



    async with _get_semaphore():

        stream = await client.chat.completions.create(

            model=settings.llm_model,

            messages=messages,

            temperature=settings.llm_temperature,

            max_tokens=settings.llm_max_tokens,

            stream=True,

        )



        try:

            async with asyncio.timeout(settings.llm_timeout_sec):

                async for chunk in stream:

                    text = _chunk_text(chunk)

                    if text:

                        yield text

        finally:

            await stream.close()

