"""Идемпотентная миграция схемы events (Phase 1 B2B-rebuild).

Добавляет 6 колонок и UNIQUE constraint для дедупликации.
Безопасна к повторному запуску — каждый ALTER обёрнут в try/except UniqueViolation.

Запуск:
    cd backend
    .\\venv\\Scripts\\python.exe scripts\\migrate_event_schema_v2.py
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.db.session import engine as async_engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# PostgreSQL error codes used to distinguish expected from unexpected failures.
DUPLICATE_OBJECT_PGCODE = "42P07"  # constraint already exists
UNIQUE_VIOLATION_PGCODE = "23505"  # data contains duplicates

NEW_COLUMNS: list[tuple[str, str]] = [
    ("time_start", "TIME NULL"),
    ("price_min", "INTEGER NULL"),
    ("price_max", "INTEGER NULL"),
    ("image_url", "TEXT NULL"),
    ("address", "TEXT NULL"),
    ("age_restriction", "VARCHAR(10) NULL"),
]

DEDUP_CONSTRAINT_NAME = "uq_events_dedup"
DEDUP_CONSTRAINT_DDL = (
    f"ALTER TABLE events ADD CONSTRAINT {DEDUP_CONSTRAINT_NAME} "
    f"UNIQUE (source_id, date_start, title)"
)


async def column_exists(conn, column: str) -> bool:
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'events' AND column_name = :col"
        ),
        {"col": column},
    )
    return result.first() is not None


async def constraint_exists(conn, name: str) -> bool:
    result = await conn.execute(
        text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE table_schema = 'public' AND table_name = 'events' AND constraint_name = :name"
        ),
        {"name": name},
    )
    return result.first() is not None


async def remove_duplicates(conn) -> int:
    """Оставляет только одну строку на (source_id, date_start, title), у которой min event_id."""
    result = await conn.execute(text("""
        DELETE FROM events e
        USING events e2
        WHERE e.source_id = e2.source_id
          AND e.date_start = e2.date_start
          AND e.title = e2.title
          AND e.event_id > e2.event_id
    """))
    return result.rowcount or 0


async def migrate() -> None:
    # Use separate transactions per DDL statement so a failure in one
    # does not roll back the others (PostgreSQL DDL is transactional).
    for col_name, col_ddl in NEW_COLUMNS:
        async with async_engine.begin() as conn:
            if await column_exists(conn, col_name):
                logger.info("column events.%s already exists — skip", col_name)
                continue
            await conn.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_ddl}"))
            logger.info("added column events.%s (%s)", col_name, col_ddl)

    async with async_engine.begin() as conn:
        exists = await constraint_exists(conn, DEDUP_CONSTRAINT_NAME)

    if exists:
        logger.info("constraint %s already exists — skip", DEDUP_CONSTRAINT_NAME)
    else:
        async with async_engine.begin() as conn:
            removed = await remove_duplicates(conn)
            logger.info("removed %d duplicate events before UNIQUE constraint", removed)

        try:
            async with async_engine.begin() as conn:
                await conn.execute(text(DEDUP_CONSTRAINT_DDL))
            logger.info("added UNIQUE constraint %s", DEDUP_CONSTRAINT_NAME)
        except (ProgrammingError, IntegrityError) as exc:
            pgcode = getattr(exc.orig, "pgcode", None)
            if pgcode in (DUPLICATE_OBJECT_PGCODE, UNIQUE_VIOLATION_PGCODE):
                logger.warning(
                    "could not add %s (pgcode=%s): unexpected duplicates remain",
                    DEDUP_CONSTRAINT_NAME, pgcode,
                )
            else:
                raise


if __name__ == "__main__":
    async def _main() -> None:
        try:
            await migrate()
        finally:
            await async_engine.dispose()

    asyncio.run(_main())
