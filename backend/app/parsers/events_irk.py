"""Парсер событий с irk.ru/afisha."""
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


async def fetch_events_irk(days_ahead: int = 30) -> list[dict[str, Any]]:
    """
    Получить список событий с irk.ru/afisha.
    
    Args:
        days_ahead: Не используется, парсим главную страницу афиши
        
    Returns:
        Список словарей с данными о событиях
    """
    url = settings.parser_irk_url
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
                    events = _parse_irk_html(html)
                else:
                    logger.warning(f"irk.ru вернул статус: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка при получении {url}: {e}")
    
    return events


def _parse_irk_html(html: str) -> list[dict[str, Any]]:
    """Парсинг HTML страницы irk.ru/afisha (обновлённая структура 2026)."""
    soup = BeautifulSoup(html, "html.parser")
    events = []
    
    date_pattern = re.compile(
        r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
        r"[,\s]+(?:пн|вт|ср|чт|пт|сб|вс)?\s*(\d{1,2}:\d{2})?",
        re.IGNORECASE
    )
    
    genres = {
        "концерт", "спектакль", "выставка", "гастроли", "спорт",
        "бизнес", "другое", "балет", "конференция", "концерт при свечах",
        "музыкальная драма", "обучение", "выставка картин", "ужин"
    }
    skip_words = {"6+", "12+", "16+", "18+", "0+", "актуальное", "скоро",
                  "все события", "показать еще", "пушкинская карта"}
    non_venue_words = {
        "купить билет", "подробнее", "экскурсия", "лекция", "мастер-класс",
        "квест", "квиз", "прогулка", "концерт", "спектакль", "выставка",
        "фестиваль", "шоу", "спорт", "бизнес", "другое", "балет",
    }
    
    # Собираем маппинг title → url из HTML-ссылок
    url_map = _build_url_map(soup)
    
    text_content = soup.get_text(separator="\n")
    lines = [line.strip() for line in text_content.split("\n") if line.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        date_match = date_pattern.search(line)
        if date_match:
            date_str = line
            title = ""
            genre = ""
            venue = ""
            
            for j in range(i - 1, max(0, i - 6), -1):
                candidate = lines[j].strip()
                candidate_lower = candidate.lower()
                
                if candidate_lower in skip_words or len(candidate) < 4:
                    continue
                if candidate_lower in genres:
                    if not genre:
                        genre = candidate
                    continue
                if re.match(r"^\d+\+$", candidate):
                    continue
                if len(candidate) > 5 and not title:
                    title = candidate
                    break
            
            # Площадка — ищем в 1-3 строках после даты (только если похоже на venue)
            _venue_markers = re.compile(
                r'театр|филармония|музей|галерея|дворец|центр|ДК|'
                r'библиотека|зал|клуб|арена|стадион|кинотеатр|'
                r'ул\.|улица|пр\.|площадь|набережная',
                re.IGNORECASE,
            )
            for j in range(i + 1, min(len(lines), i + 4)):
                candidate = lines[j].strip()
                candidate_lower = candidate.lower()
                if candidate_lower in skip_words or len(candidate) < 3:
                    continue
                if date_pattern.search(candidate):
                    break
                if re.match(r"^\d+\+$", candidate) or candidate_lower in genres:
                    continue
                if candidate_lower in non_venue_words:
                    continue
                if _venue_markers.search(candidate) and 3 < len(candidate) < 80:
                    venue = candidate
                    break
            
            if title and len(title) > 3 and title.lower() not in skip_words:
                event_date = _parse_irk_date(date_str)
                event_id = generate_event_id(title, event_date, "irk")
                event_url = url_map.get(title.lower(), "https://irk.ru/afisha/")
                location = venue if venue else "Иркутск"
                
                events.append({
                    "id": event_id,
                    "title": title,
                    "description": None,
                    "date_start": event_date,
                    "event_type": detect_event_type(title, genre),
                    "location": location,
                    "url": event_url,
                    "source": "irk",
                })
        
        i += 1
    
    seen_titles = set()
    unique_events = []
    for event in events:
        title_key = event["title"].lower()[:30]
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_events.append(event)
    
    return unique_events


def _build_url_map(soup: BeautifulSoup) -> dict[str, str]:
    """Извлечь маппинг title→url из ссылок на странице."""
    url_map: dict[str, str] = {}
    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if href.startswith("/"):
            href = f"https://irk.ru{href}"
        if "irk.ru" in href and "/afisha/" in href:
            url_map[text.lower()] = href
    return url_map


def _parse_irk_date(date_str: str) -> str:
    """
    Парсинг даты в формате irk.ru.
    
    Примеры входных данных:
    - "3 февраля, вт 20:40"
    - "18 мая, вс 18:00"
    - "23 мая, пт 19:00"
    
    Returns:
        Дата в формате YYYY-MM-DD
    """
    if not date_str:
        return str(date.today())
    
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
                return str(date.today())
            
            today = date.today()
            year = today.year
            if month < today.month or (month == today.month and day < today.day):
                year += 1
            
            return f"{year}-{month:02d}-{day:02d}"
    except Exception as e:
        logger.error(f"Ошибка парсинга даты '{date_str}': {e}")
    
    return str(date.today())


def generate_event_id(title: str, date_str: str, source: str = "irk") -> str:
    """Генерация уникального ID события."""
    content = f"{source}_{date_str}_{title}"
    return f"{source}_{hashlib.md5(content.encode()).hexdigest()[:12]}"
