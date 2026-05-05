"""Парсер событий с irk.zeroevent.ru — крупные мероприятия Иркутска."""
import aiohttp
import asyncio
import json
import logging
import re
import hashlib
from datetime import datetime, date
from typing import Any

from app.config import settings
from app.parsers.base import detect_event_type

logger = logging.getLogger(__name__)

# Rate limiting между запросами
RATE_LIMIT_DELAY = 0.5  # секунд

_PRICE_MIN_RE = re.compile(
    r"от\s+(\d{2,5})\s*(?:₽|руб(?:лей|ля)?\.?|р\.?)(?:\b|(?=\s|,|$))",
    re.IGNORECASE,
)


def _extract_price_min(text: str | None) -> int | None:
    """Возвращает min цену из текста (RU formats: 'от N руб', 'от N₽')."""
    if not text:
        return None
    m = _PRICE_MIN_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (ValueError, TypeError):
        return None


async def fetch_events_zeroevent(years: list[int] | None = None, by_month: bool = True) -> list[dict[str, Any]]:
    """
    Получить события с irk.zeroevent.ru.
    
    Этот источник содержит крупные события (концерты, спектакли, балеты)
    с точными датами. Данные доступны в формате JSON-LD schema.org.
    
    Args:
        years: Список годов для парсинга (по умолчанию текущий и предыдущий)
        by_month: Если True, парсит по месяцам (больше событий)
        
    Returns:
        Список событий в формате для БД
    """
    if years is None:
        current_year = date.today().year
        years = [current_year - 1, current_year]  # 2025, 2026
    
    all_events = []
    seen_ids = set()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    # Названия месяцев для URL
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december"
    ]
    
    async with aiohttp.ClientSession() as session:
        for year in years:
            # Парсим по годам
            url = f"https://irk.zeroevent.ru/{year}"
            events = await _fetch_and_parse(session, url, headers, year)
            for e in events:
                if e["id"] not in seen_ids:
                    all_events.append(e)
                    seen_ids.add(e["id"])
            logger.info(f"zeroevent.ru/{year}: {len(events)} событий")
            await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting

            # Также парсим по месяцам для полноты
            if by_month:
                for month_name in months:
                    url = f"https://irk.zeroevent.ru/{month_name}"
                    events = await _fetch_and_parse(session, url, headers, year)
                    new_count = 0
                    for e in events:
                        if e["id"] not in seen_ids:
                            all_events.append(e)
                            seen_ids.add(e["id"])
                            new_count += 1
                    if new_count > 0:
                        logger.info(f"zeroevent.ru/{month_name}: +{new_count} новых событий")
                    await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting
    
    return all_events


async def _fetch_and_parse(session, url: str, headers: dict, year: int) -> list[dict[str, Any]]:
    """Загрузить и распарсить страницу."""
    try:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=10),
            ssl=settings.parser_ssl_verify,
        ) as response:
            if response.status == 200:
                html = await response.text()
                return _parse_zeroevent_html(html, year)
    except Exception as e:
        logger.error(f"Ошибка при получении {url}: {e}")
    return []


def _parse_zeroevent_html(html: str, year: int) -> list[dict[str, Any]]:
    """
    Извлечь события из JSON-LD блока на странице zeroevent.
    
    Структура JSON-LD:
    {
        "@context": "http://schema.org",
        "@graph": [
            {
                "@type": "Event",
                "name": "Концерт Полины Гагариной",
                "startDate": "2025-05-23T16:00:00Z",
                "location": {
                    "@type": "Place",
                    "name": "Ледовый дворец «Айсберг»",
                    "address": ["Иркутск, улица Лермонтова, дом 255/1", ...]
                },
                "description": "...",
                "image": "...",
                "url": "..."
            },
            ...
        ]
    }
    """
    events = []
    
    # Ищем JSON-LD блок
    pattern = r'<script type="application/ld\+json">(\{.*?\})</script>'
    match = re.search(pattern, html, re.DOTALL)
    
    if not match:
        return events
    
    try:
        data = json.loads(match.group(1))
        graph = data.get("@graph", [])
        
        for item in graph:
            if item.get("@type") != "Event":
                continue
            
            name = item.get("name", "").strip()
            if not name:
                continue
            
            start_date_str = item.get("startDate", "")
            try:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00")).date()
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning(f"Failed to parse start date: {e}")
                start_date = None
            
            if start_date is None:
                continue
            
            # date_end из JSON-LD
            end_date_str = item.get("endDate", "")
            end_date = None
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00")).date()
                except (ValueError, AttributeError, TypeError) as e:
                    logger.warning(f"Failed to parse end date: {e}")
            
            location_data = item.get("location", {})
            location_name = location_data.get("name", "")
            location_address = location_data.get("address", [])
            
            # Собираем location: "Площадка, адрес"
            location = _build_location(location_name, location_address)
            
            content = f"zeroevent_{start_date}_{name}"
            event_id = f"zeroevent_{hashlib.md5(content.encode()).hexdigest()[:12]}"
            description = _clean_html(item.get("description", ""))
            price_min = _extract_price_min(description) if description else None

            events.append({
                "id": event_id,
                "title": name,
                "description": description,
                "date_start": str(start_date),
                "date_end": str(end_date) if end_date else None,
                "event_type": detect_event_type(name),
                "location": location,
                "source": "zeroevent",
                "url": item.get("url", ""),
                "image_url": item.get("image", ""),
                "price_min": price_min,
            })
    
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON-LD: {e}")
    except Exception as e:
        logger.error(f"Ошибка обработки zeroevent данных: {e}")
    
    return events


def _build_location(venue: str, address_data: Any) -> str:
    """Собрать location из названия площадки и адреса."""
    addr = ""
    if isinstance(address_data, list) and address_data:
        raw = address_data[0] if isinstance(address_data[0], str) else ""
        # Убираем дублирование города в адресе
        addr = re.sub(r"^Иркутск,?\s*", "", raw).strip()
    elif isinstance(address_data, str):
        addr = re.sub(r"^Иркутск,?\s*", "", address_data).strip()
    
    if venue and addr:
        return f"{venue}, {addr}"
    return venue or addr or "Иркутск"


def _clean_html(text: str) -> str:
    """Очистить текст от HTML-entities и тегов."""
    if not text:
        return ""
    import html as html_mod
    clean = html_mod.unescape(text)
    clean = re.sub(r'<[^>]+>', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:500]
