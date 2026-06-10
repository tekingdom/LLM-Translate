from pydantic import BaseModel


class StatsResponse(BaseModel):
    total_messages: int
    total_tokens_in: int
    total_tokens_out: int
    cache_hits: int
    cache_total: int
    cache_hit_rate: float
