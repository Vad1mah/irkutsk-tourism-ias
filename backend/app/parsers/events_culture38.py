"""Парсер событий с culture38.ru."""
import logging
import aiohttp
from bs4 import BeautifulSoup
from datetime import date
from typing import Any
import re
import hashlib

from app.config import settings
from app.parsers.base import detect_event_type

logger = logging.getLogger(__name__)


async def fetch_events_culture38(days_ahead: int = 30) -> list[dict[str, Any]]:
    """
    Получить список событий с culture38.ru.
    
    Args:
        days_ahead: Количество дней для поиска событий вперёд
        
    Returns:
        Список словарей с данными о событиях
    """
    url = f"{settings.parser_culture38_url}afisha/"
    events = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=settings.parser_timeout),
                ssl=settings.parser_ssl_verify,
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    events = _parse_culture38_html(html)
    except Exception as e:
        logger.error(f"Ошибка при получении {url}: {e}")
    
    return events


def _parse_culture38_html(html: str) -> list[dict[str, Any]]:
    """Парсинг HTML страницы culture38.ru/afisha."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    # Ищем ссылки на события
    links = soup.find_all("a", href=re.compile(r"/afisha/[^/]+/?$"))
    
    _MONTHS = (
        r'(?:января|февраля|марта|апреля|мая|июня|июля|августа|'
        r'сентября|октября|ноября|декабря)'
    )
    _date_prefix_re = re.compile(
        rf'^(?:с\s+|по\s+|до\s+)?'
        rf'\d{{1,2}}(?:\s*[-–—]\s*\d{{1,2}})?\s*{_MONTHS}'
        rf'(?:\s+(?:по|до)\s+\d{{1,2}}\s+{_MONTHS})?'
        rf'(?:\s+\d{{4}})?'
        rf'\s*',
        re.IGNORECASE,
    )

    for link in links:
        href = link.get("href", "")
        raw_title = link.get_text(strip=True)
        
        if not raw_title or len(raw_title) < 3:
            continue
        if raw_title.lower() in ["все", "сегодня", "завтра", "выходные", "еще",
                                   "пушкинская карта"]:
            continue
        
        # Убираем дату из начала title ("15 – 22 мартаТекст" → "Текст")
        title = _date_prefix_re.sub("", raw_title).strip()
        if not title or len(title) < 3:
            title = raw_title
        
        # Ищем дату и площадку из окружающего контекста
        parent = link.parent
        date_str = ""
        location = "Иркутская область"
        if parent:
            # Дата — обычно в предыдущем sibling
            prev_sib = parent.find_previous_sibling()
            if prev_sib:
                text = prev_sib.get_text(strip=True)
                if re.search(r"\d+\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", text.lower()):
                    date_str = text
            _venue_re = re.compile(
                r'театр|филармония|музей|галерея|дворец|центр|ДК|библиотека|зал|клуб',
                re.IGNORECASE,
            )
            _has_date_re = re.compile(
                r'\d{1,2}\s*(?:января|февраля|марта|апреля|мая|июня|'
                r'июля|августа|сентября|октября|ноября|декабря)',
                re.IGNORECASE,
            )
            next_sib = parent.find_next_sibling()
            if next_sib:
                venue_text = next_sib.get_text(strip=True)
                if (venue_text and _venue_re.search(venue_text)
                        and not _has_date_re.search(venue_text)
                        and len(venue_text) < 80):
                    location = venue_text
        
        full_url = f"https://culture38.ru{href}" if href.startswith("/") else href
        event_date = _parse_culture38_date(date_str) if date_str else None
        event_id = _generate_event_id(title, "culture38", event_date or "")
        
        if event_date is None:
            continue
        
        events.append({
            "id": event_id,
            "title": title,
            "description": None,
            "date_start": event_date,
            "event_type": detect_event_type(title),
            "location": location,
            "url": full_url,
            "source": "culture38",
        })
    
    # Удаляем дубликаты
    seen = set()
    unique_events = []
    for e in events:
        key = e["title"].lower()[:30]
        if key not in seen:
            seen.add(key)
            unique_events.append(e)
    
    return unique_events


def _parse_culture38_date(date_str: str) -> str | None:
    """Парсинг даты culture38. Возвращает None при неудаче."""
    if not date_str:
        return None
    
    months = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }
    
    try:
        match = re.search(r"(\d{1,2})\s+(\w+)", date_str.lower())
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            month = months.get(month_name)
            if not month or day < 1 or day > 31:
                logger.warning(f"Failed to parse date '{date_str}': invalid day/month")
                return None
            
            today = date.today()
            year = today.year
            if month < today.month or (month == today.month and day < today.day):
                year += 1
            
            return f"{year}-{month:02d}-{day:02d}"
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
    
    return None


def _generate_event_id(title: str, source: str, date_str: str = "") -> str:
    """Генерация уникального ID события."""
    content = f"{source}_{title}_{date_str}"
    return f"{source}_{hashlib.md5(content.encode()).hexdigest()[:12]}"
