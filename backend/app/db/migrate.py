"""Applies schema.sql against DATABASE_URL. Safe to run repeatedly (IF NOT EXISTS everywhere)."""

import asyncio
from pathlib import Path

import asyncpg

from app.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def run_migrations() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = await asyncpg.connect(dsn=settings.database_url)
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migrations())
