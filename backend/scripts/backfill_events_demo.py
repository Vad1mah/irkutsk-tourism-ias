"""Разовый локальный backfill событий для демо/защиты.

Тяжёлые парсеры (yandex/kassir — Crawl4AI/headless-браузер; telegram — Telethon+MTProxy)
НЕ работают в прод-контейнере: в образе нет браузера (выпилен из-за disk-лимита cloud.ru),
а t.me заблокирован на сетевом уровне в РФ. Этот скрипт собирает такие источники ЛОКАЛЬНО
(где браузер есть и блокировка обходится) и пишет напрямую в БД из DATABASE_URL.

Не сервис, а одноразовый инструмент — после защиты данные снова устареют, перезапусти при
необходимости. Для постоянно работающих источников (irk, zeroevent) почини scheduler-сейв
(см. _build_event_row в db_service.py) и дай прод-контейнеру собирать их по cron.

Примеры:
    # Сухой прогон — собрать и показать, НИЧЕГО не писать:
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/backfill_events_demo.py

    # Записать в локальную БД (DATABASE_URL из .env):
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/backfill_events_demo.py --write

    # Записать в ПРОД через SSH-туннель к его PostgreSQL:
    #   терминал 1:  ssh -L 5433:localhost:5432 user1@82.202.143.11   # держать открытым
    #   терминал 2:  DATABASE_URL='postgresql+asyncpg://tourism:ПАРОЛЬ@localhost:5433/tourism' \
    #                PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/backfill_events_demo.py --write

    # Дамп в JSON (например, чтобы импортировать на сервере):
    PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe scripts/backfill_events_demo.py --out events_backfill.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Запуск из каталога scripts/ — добавляем корень backend в путь.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_events")

DEFAULT_SOURCES = ["irk", "yandex", "kassir"]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Разовый локальный backfill событий в БД.")
    p.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help=f"CSV источников (по умолчанию {','.join(DEFAULT_SOURCES)}).",
    )
    p.add_argument("--write", action="store_true", help="Записать в БД из DATABASE_URL.")
    p.add_argument("--out", default=None, help="Сохранить собранное в JSON-файл.")
    p.add_argument(
        "--include-past",
        action="store_true",
        help="Не отфильтровывать прошедшие события (по умолчанию оставляем только date_start >= сегодня).",
    )
    return p.parse_args()


def _masked_db_target() -> str:
    """Хост:порт текущего DATABASE_URL без креденшелов — чтобы видеть КУДА пишем."""
    try:
        from app.config import settings

        raw = settings.database_url.get_secret_value()
        tail = raw.rsplit("@", 1)[-1]  # host:port/db
        return tail
    except Exception:
        return "<unknown>"


async def _run() -> int:
    args = _parse_args()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    from app.parsers import fetch_all_events

    logger.info("Сбор событий из источников: %s", sources)
    events = await fetch_all_events(sources=sources, use_ai=True)
    logger.info("Парсеры вернули всего: %d событий", len(events))

    if not args.include_past:
        today = date.today().isoformat()
        before = len(events)
        events = [e for e in events if (getattr(e, "date_start", "") or "") >= today]
        logger.info("Отфильтровано прошедших: %d → осталось будущих: %d", before, len(events))

    if not events:
        logger.warning("Нет событий к записи. Выход.")
        return 0

    by_src = Counter(getattr(e, "source", "?") for e in events)
    logger.info("По источникам: %s", dict(by_src))
    for e in events[:8]:
        logger.info("  %s | %s | %s", e.date_start, (e.title or "")[:48], e.source)

    if args.out:
        payload = [e.model_dump(mode="json") for e in events]
        Path(args.out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("JSON-дамп: %s (%d событий)", args.out, len(payload))

    if args.write:
        from app.services.db_service import db_service

        target = _masked_db_target()
        logger.info("Запись в БД → %s ...", target)
        saved = await db_service.upsert_events_batch(events)
        logger.info("Готово: upsert обработал %d строк в %s", saved, target)
    elif not args.out:
        logger.info(
            "Сухой прогон: ничего не записано. Добавь --write (в БД) или --out FILE (в JSON)."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
