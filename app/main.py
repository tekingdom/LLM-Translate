from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import async_session, ensure_schema, engine
from app.routers import cache, config_api, conversations, messages, pages, prompts, stats
from app.services.prompts import seed_default_prompts

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_schema()
    async with async_session() as session:
        await seed_default_prompts(session)
        await session.commit()
    yield
    await engine.dispose()


app = FastAPI(
    title="LLM Translate",
    description="Conversational translation service with Local LLM support (en/zh/th)",
    version="0.1.0",
    lifespan=lifespan,
)

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
