import hashlib
from functools import lru_cache
from pathlib import Path

_STATIC_DIR = Path(__file__).parent / "static"


@lru_cache
def static_version(filename: str) -> str:
    path = _STATIC_DIR / filename
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    return digest[:8]
