import tiktoken

_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_encoder().encode(text))


def calc_tokens_per_sec(tokens: int, latency_ms: int) -> float:
    if latency_ms <= 0 or tokens <= 0:
        return 0.0
    return round(tokens / (latency_ms / 1000.0), 2)
