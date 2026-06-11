import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import get_settings, warn_if_insecure_production_settings
from app.database import async_session, ensure_schema, engine
from app.routers import cache, config_api, conversations, messages, pages, prompts, stats
from app.services.prompts import seed_default_prompts, warm_prompt_cache

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    warn_if_insecure_production_settings(settings)
    await ensure_schema()
    async with async_session() as session:
        await seed_default_prompts(session)
        await warm_prompt_cache(session)
        await session.commit()
    yield
    await engine.dispose()


app = FastAPI(
    title="LLM Translate",
    description="Conversational translation service with Local LLM support (en/zh/th)",
    version="0.1.0",
    lifespan=lifespan,
)

health_router = APIRouter(tags=["health"])


@health_router.get("/health/live")
async def health_live():
    return {"status": "ok"}


@health_router.get("/health/ready")
async def health_ready():
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("Database readiness check failed")
        checks["database"] = "error"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.llm_base_url.rstrip('/')}/models")
            if response.status_code < 500:
                checks["llm"] = "ok"
            else:
                checks["llm"] = "error"
    except Exception:
        logger.exception("LLM readiness check failed")
        checks["llm"] = "error"

    if any(status == "error" for status in checks.values()):
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})

    return {"status": "ready", "checks": checks}


app.include_router(health_router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(prompts.router)
app.include_router(cache.router)
app.include_router(stats.router)
app.include_router(config_api.router)
app.include_router(pages.router)


def run():
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )


if __name__ == "__main__":
    run()
