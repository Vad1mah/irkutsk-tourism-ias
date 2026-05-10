"""CLI для batch-реклассификации событий с event_type='event' через Mistral.

Usage:
    python scripts/reclassify_events.py             # полный прогон + UPDATE в БД
    python scripts/reclassify_events.py --dry-run   # печатает решения, не трогает БД
    python scripts/reclassify_events.py --limit 30  # ограничить N событий
    python scripts/reclassify_events.py --concurrency 5  # параллельных запросов

Использует существующий llm_service.extract_structured(), который под капотом
вызывает Mistral с response_format=json_schema (см. _call_mistral в llm_service).
"""
import argparse
import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

# Позволяем запускать как `python scripts/reclassify_events.py` из backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import text  # noqa: E402

from app.services.llm_service import llm_service  # noqa: E402
from app.services.db_service import db_service  # noqa: E402
from app.db import session as session_module  # noqa: E402

logger = logging.getLogger("reclassify_events")

VALID_CATEGORIES = [
    "concert", "theater", "exhibition", "festival", "sport",
    "business", "cinema", "kids", "holiday", "tour", "lecture", "event",
]

SYSTEM_PROMPT = """Ты — классификатор событий культурно-туристического реестра Иркутской области.
Получаешь название события и источник (afisha-сайт или Telegram-канал) — возвращаешь одну категорию.

Категории:
- concert: концерты, музыкальные выступления, шоу
- theater: спектакли, балет, опера, мюзиклы
- exhibition: выставки, экспозиции, вернисажи
- festival: фестивали, ярмарки, карнавалы
- sport: соревнования, турниры, забеги
- business: конференции, форумы, тренинги, мастер-классы
- cinema: кинопоказы, премьеры
- kids: детские мероприятия, семейные события
- holiday: календарные праздники (День города, Новый год, юбилеи)
- tour: экскурсии, туры, пешеходные маршруты, сплавы
- lecture: лекции, литературные вечера, образовательные встречи
- event: используй ТОЛЬКО если это спам, приветствие или неклассифицируемая запись
  (примеры: "АКТИВНОЙ СУББОТЫ!", "ПРЕКРАСНОЙ СРЕДЫ!", "Тойнак" без контекста).

Правила:
1. Если название содержит явный жанр (концерт/выставка/лекция) — используй его.
2. Если из Telegram (source начинается с tg_) и текст похож на приветствие — event.
3. Если есть имя артиста/коллектива и источник — kassir/yandex/afisha — скорее всего concert.
4. Если есть слово "Тур", "Экскурсия", "Маршрут", "Сплав" — tour.

Верни только JSON: {"category": "<one_of_categories>", "confidence": <0..1>}.
"""

JSON_SCHEMA = {
    "properties": {
        "category": {"type": "string", "enum": VALID_CATEGORIES},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["category", "confidence"],
    "additionalProperties": False,
}


async def classify_one(event_id: str, title: str, source: str) -> tuple[str, str, float]:
    """Классифицирует одно событие. Возвращает (event_id, category, confidence).

    При ошибке fallback к ('event', 0.0) — событие останется в исходной категории.
    """
    user_text = f'title: "{title}"\nsource: "{source}"'
    try:
        result = await llm_service.extract_structured(
            text=user_text,
            schema=JSON_SCHEMA,
            system_prompt=SYSTEM_PROMPT,
        )
        if "error" in result:
            logger.warning("classify error for %s: %s", event_id, result.get("error"))
            return event_id, "event", 0.0

        cat = str(result.get("category", "event")).strip().lower()
        try:
            conf = float(result.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5

        if cat not in VALID_CATEGORIES:
            logger.warning("unknown category %r for %s, fallback to event", cat, event_id)
            cat = "event"
        return event_id, cat, conf
    except Exception as e:  # noqa: BLE001
        logger.warning("classify failed for %s: %s", event_id, e)
        return event_id, "event", 0.0


async def main(limit: int | None, dry_run: bool, concurrency: int) -> None:
    # Поднимаем пул и инициализируем LLM
    await db_service.connect()
    if getattr(llm_service, "_client", None) is None:
        llm_service.init()

    async_session = session_module.async_session  # ленивый getattr → factory

    query = "SELECT event_id, title, source_id FROM events WHERE event_type = 'event'"
    if limit:
        query += f" LIMIT {int(limit)}"

    async with async_session() as s:
        rows = (await s.execute(text(query))).all()

    logger.info("Loaded %d events with event_type='event'", len(rows))
    if not rows:
        return

    sem = asyncio.Semaphore(max(1, concurrency))

    async def bounded(eid: str, title: str, src: str) -> tuple[str, str, float]:
        async with sem:
            return await classify_one(eid, title, src)

    results = await asyncio.gather(*[bounded(r[0], r[1], r[2]) for r in rows])

    cats = Counter(r[1] for r in results)
    logger.info("Classification distribution: %s", dict(cats))

    if dry_run:
        for eid, cat, conf in results[:30]:
            print(f"  {eid:30} -> {cat:12} (conf={conf:.2f})")
        if len(results) > 30:
            print(f"  ... и ещё {len(results) - 30} записей")
        print(f"... total {len(results)} reclassified (dry-run, no DB write)")
        return

    updated = 0
    skipped = 0
    async with async_session() as s:
        for eid, cat, _conf in results:
            if cat == "event":
                skipped += 1
                continue
            await s.execute(
                text(
                    "UPDATE events SET event_type = :c, updated_at = NOW() "
                    "WHERE event_id = :id"
                ),
                {"c": cat, "id": eid},
            )
            updated += 1
        await s.commit()
    logger.info("DB updated: %d reclassified, %d remained as 'event'", updated, skipped)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Batch reclassify events with event_type='event' via Mistral LLM."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max number of events to process (default: all).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print results without updating the database.",
    )
    parser.add_argument(
        "--concurrency", type=int, default=10,
        help="Max parallel LLM requests (default: 10).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.limit, args.dry_run, args.concurrency))
