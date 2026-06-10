"""Run Alembic migrations; stamp head when tables exist without version tracking."""

import asyncio
import subprocess
import sys

from sqlalchemy import inspect

from app.config import get_settings
from app.database import engine

REQUIRED_TABLES = frozenset(
    {"conversations", "messages", "translation_cache", "prompts", "app_config"}
)


async def _schema_tables() -> set[str]:
    settings = get_settings()

    def _list(sync_conn) -> set[str]:
        inspector = inspect(sync_conn)
        return set(inspector.get_table_names(schema=settings.db_schema))

    async with engine.connect() as conn:
        return await conn.run_sync(_list)


async def _has_alembic_version() -> bool:
    settings = get_settings()

    def _check(sync_conn) -> bool:
        inspector = inspect(sync_conn)
        return inspector.has_table("alembic_version", schema=settings.db_schema)

    async with engine.connect() as conn:
        return await conn.run_sync(_check)


async def main() -> None:
    tables = await _schema_tables()
    if REQUIRED_TABLES.issubset(tables) and not await _has_alembic_version():
        print(
            "Schema tables already exist without Alembic version tracking; stamping head..."
        )
        subprocess.check_call([sys.executable, "-m", "alembic", "stamp", "head"])
        if not await _has_alembic_version():
            raise RuntimeError(
                "Alembic stamp did not persist; check database permissions and alembic/env.py"
            )
    else:
        subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "head"])
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
