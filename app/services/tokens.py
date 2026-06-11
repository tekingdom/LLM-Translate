import asyncio

import tiktoken

_encoder: tiktoken.Encoding | None = None
_ASYNC_TOKEN_THRESHOLD = 1024


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_encoder().encode(text))


async def count_tokens_async(text: str) -> int:
    if not text:
        return 0
    if len(text) < _ASYNC_TOKEN_THRESHOLD:
        return count_tokens(text)
    return await asyncio.to_thread(count_tokens, text)


def calc_tokens_per_sec(tokens: int, latency_ms: int) -> float:
    if latency_ms <= 0 or tokens <= 0:
        return 0.0
    return round(tokens / (latency_ms / 1000.0), 2)
