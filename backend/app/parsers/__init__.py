"""Пакет парсеров данных для туристической аналитики Байкала.

Источники данных:
- События: zeroevent, culture38, irk.ru, Яндекс Афиша, Kassir.ru, Культура РФ, Telegram
- Отели: 101hotels.com (загрузка, цены), Xotelo/TripAdvisor (рейтинги, метаданные)
- Погода: OpenMeteo
- Крупные события: ручной сбор
- Турбазы и отели: AI extraction

Технологии парсинга:
- aiohttp + BeautifulSoup: статические страницы
- Crawl4AI: AI-powered extraction, JavaScript-heavy сайты
- Jina Reader: бесплатный Markdown API
- Telethon: Telegram каналы
- Xotelo REST API: метаданные отелей (TripAdvisor)
"""
import logging
from datetime import date
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

# === Существующие парсеры ===
from app.parsers.events_culture38 import fetch_events_culture38
from app.parsers.events_irk import fetch_events_irk
from app.parsers.events_zeroevent import fetch_events_zeroevent
from app.parsers.events_major import get_major_events_2025_2026, get_school_holidays_2025_2026

# === Новые парсеры ===
# События
from app.parsers.events_yandex import fetch_events_yandex, YandexAfishaParser
from app.parsers.events_kassir import fetch_events_kassir, KassirParser
from app.parsers.events_culture_rf import fetch_events_culture_rf, CultureRFParser
from app.parsers.events_telegram import (
    fetch_events_telegram,
    TelegramEventParser,
    TelegramWebParser,
    BAIKAL_CHANNELS,
)

# AI extraction
from app.parsers.ai_extractor import (
    AIEventExtractor,
    fetch_markdown_jina,
    extract_events_simple,
    extract_events_from_resorts,
    BAIKAL_RESORT_SITES,
    CRAWL4AI_AVAILABLE,
)

# Базовые классы
from app.parsers.base import (
    ParsedEvent,
    ParserConfig,
    BaseParser,
    parse_russian_date,
    detect_event_type,
    RUSSIAN_MONTHS,
)

# Отели
from app.parsers.hotels_101hotels import parse_and_save_hotels
from app.parsers.hotels_xotelo import (
    fetch_hotels_xotelo,
    cross_reference,
    parse_and_save_xotelo,
)

__all__ = [
    # Существующие
    "fetch_events_culture38",
    "fetch_events_irk",
    "fetch_events_zeroevent",
    "get_major_events_2025_2026",
    "get_school_holidays_2025_2026",

    # Новые события
    "fetch_events_yandex",
    "fetch_events_kassir",
    "fetch_events_culture_rf",
    "fetch_events_telegram",
    "YandexAfishaParser",
    "KassirParser",
    "CultureRFParser",
    "TelegramEventParser",
    "TelegramWebParser",
    "BAIKAL_CHANNELS",

    # AI extraction
    "AIEventExtractor",
    "fetch_markdown_jina",
    "extract_events_simple",
    "extract_events_from_resorts",
    "BAIKAL_RESORT_SITES",
    "CRAWL4AI_AVAILABLE",

    # Базовые классы
    "ParsedEvent",
    "ParserConfig",
    "BaseParser",
    "parse_russian_date",
    "detect_event_type",
    "RUSSIAN_MONTHS",

    # Отели
    "parse_and_save_hotels",
    "fetch_hotels_xotelo",
    "cross_reference",
    "parse_and_save_xotelo",
]


async def _run_standalone_with_health(
    parser_id: str,
    fn: Callable[..., Coroutine[Any, Any, list]],
    *args: Any,
    **kwargs: Any,
) -> list:
    """Обёртка для standalone-парсеров (не BaseParser) с отчётом в health service."""
    from app.services.parser_health_service import parser_health_service, sanitize_error
    try:
        items = await fn(*args, **kwargs)
        await parser_health_service.report(
            parser_id=parser_id,
            status="ok",
            items_collected=len(items),
        )
        return items
    except Exception as exc:
        await parser_health_service.report(
            parser_id=parser_id,
            status="fail",
            items_collected=0,
            error=sanitize_error(str(exc))[:500],
        )
        raise


async def fetch_all_events(
    sources: list[str] | None = None,
    use_ai: bool = True
) -> list[ParsedEvent]:
    """
    Получить события из всех источников.

    Args:
        sources: Список источников (по умолчанию все)
        use_ai: Использовать AI extraction где возможно

    Returns:
        Список всех событий (deduplicated)
    """
    import asyncio

    all_sources = sources or [
        "zeroevent", "culture38", "irk", "major",
        "yandex", "kassir", "culture_rf", "telegram"
    ]

    all_events = []
    seen_titles = set()

    tasks = []

    if "zeroevent" in all_sources:
        tasks.append(("zeroevent", _run_standalone_with_health("zeroevent", fetch_events_zeroevent)))
    if "culture38" in all_sources:
        tasks.append(("culture38", _run_standalone_with_health("culture38", fetch_events_culture38)))
    if "irk" in all_sources:
        tasks.append(("irk", _run_standalone_with_health("irk", fetch_events_irk)))
    if "yandex" in all_sources:
        # health-id = config.name парсера ("yandex_afisha"), иначе при timeout/exception
        # появится фантомный дубль "yandex" рядом с внутренним "yandex_afisha".
        tasks.append(("yandex_afisha", fetch_events_yandex(use_ai=use_ai)))
    if "kassir" in all_sources:
        tasks.append(("kassir", fetch_events_kassir(use_ai=use_ai)))
    if "culture_rf" in all_sources:
        tasks.append(("culture_rf", fetch_events_culture_rf()))
    if "telegram" in all_sources:
        tasks.append(("telegram", _run_standalone_with_health("telegram", fetch_events_telegram, use_telethon=False)))

    # Запускаем параллельно с timeout для каждого парсера (120s — Jina-fallback медленный)
    from app.services.parser_health_service import parser_health_service, sanitize_error
    wrapped_tasks = [
        asyncio.wait_for(t[1], timeout=120)
        for t in tasks
    ]
    results = await asyncio.gather(*wrapped_tasks, return_exceptions=True)
    
    for i, result in enumerate(results):
        source_name = tasks[i][0]
        if isinstance(result, asyncio.TimeoutError):
            logger.error(f"Парсер {source_name}: таймаут 120с — пропущен")
            await parser_health_service.report(
                parser_id=source_name, status="fail", items_collected=0,
                error="timeout 120s (нет ответа источника/браузера)",
            )
            continue
        if isinstance(result, Exception):
            logger.error(f"Ошибка парсера {source_name}: {result}")
            await parser_health_service.report(
                parser_id=source_name, status="fail", items_collected=0,
                error=sanitize_error(str(result))[:500],
            )
            continue
        
        for event in result:
            # Получаем title и дату в зависимости от типа
            if isinstance(event, ParsedEvent):
                title = event.title
                ds = event.date_start
            elif isinstance(event, dict):
                title = event.get("title", "")
                ds = event.get("date_start")
            else:
                continue

            if not title:
                continue

            # Дедуп по (полный нормализованный title, дата) — не по title[:50],
            # иначе разные события с общим префиксом >50 символов схлопываются.
            title_key = (title.lower().strip(), str(ds or ""))
            if title_key not in seen_titles:
                if isinstance(event, ParsedEvent):
                    all_events.append(event)
                else:
                    # Конвертируем dict в ParsedEvent — переносим ВСЕ поля,
                    # иначе теряются time_start/price_*/image_url/address/age_restriction.
                    try:
                        all_events.append(ParsedEvent(
                            id=event.get("id", f"auto-{hash(title)}"),
                            title=title,
                            description=event.get("description"),
                            date_start=event.get("date_start", str(date.today())),
                            date_end=event.get("date_end"),
                            time_start=event.get("time_start"),
                            event_type=event.get("event_type", "event"),
                            location=event.get("location", "Иркутск"),
                            address=event.get("address"),
                            price=event.get("price"),
                            price_min=event.get("price_min"),
                            price_max=event.get("price_max"),
                            source=source_name,
                            url=event.get("url"),
                            image_url=event.get("image_url"),
                            age_restriction=event.get("age_restriction"),
                            category=event.get("category"),
                            tags=event.get("tags", []),
                        ))
                    except Exception as e:
                        logger.error(f"Ошибка конвертации события: {e}")
                seen_titles.add(title_key)
    
    # Добавляем major events
    if "major" in all_sources:
        major_events = get_major_events_2025_2026()
        for event in major_events:
            title_key = (event["title"].lower().strip(), str(event.get("date_start") or ""))
            if title_key not in seen_titles:
                try:
                    all_events.append(ParsedEvent(
                        id=event["id"],
                        title=event["title"],
                        description=event.get("description", ""),
                        date_start=event["date_start"],
                        date_end=event.get("date_end"),
                        time_start=event.get("time_start"),
                        event_type=event.get("event_type", "event"),
                        location=event.get("location", "Иркутск"),
                        address=event.get("address"),
                        price=event.get("price"),
                        price_min=event.get("price_min"),
                        price_max=event.get("price_max"),
                        source="major",
                        url=event.get("url"),
                        image_url=event.get("image_url"),
                        age_restriction=event.get("age_restriction"),
                        category=event.get("category"),
                        tags=event.get("tags", []),
                    ))
                except Exception as e:
                    logger.error(f"Failed to convert major event: {e}")
                seen_titles.add(title_key)
    
    logger.info(f"Всего событий: {len(all_events)} из {len(all_sources)} источников")
    return all_events
