import asyncio
import os

from sqlalchemy import text

from app.config import get_settings
from app.database import engine

settings = get_settings()


async def main() -> None:
    print("DATABASE_URL:", settings.database_url.replace(settings.database_url.split("@")[0].split("//")[1], "***"))
    print("In Docker:", os.path.exists("/.dockerenv"))
    async with engine.connect() as conn:
        r = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :schema ORDER BY tablename"),
            {"schema": settings.db_schema},
        )
        tables = [row[0] for row in r]
        print(f"Tables in {settings.db_schema}:", tables)
        r2 = await conn.execute(
            text(
                "SELECT version_num FROM llm_translate.alembic_version"
                if "alembic_version" in tables
                else "SELECT 1 WHERE false"
            )
        )
        if r2.returns_rows:
            print("Alembic version:", r2.scalar())


if __name__ == "__main__":
    asyncio.run(main())
