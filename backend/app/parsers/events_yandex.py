"""Парсер событий с Яндекс Афиши.

Яндекс Афиша (afisha.yandex.ru/irkutsk) содержит:
- Концерты, спектакли, выставки
- Точные даты и цены
- Площадки и адреса

Методы извлечения:
1. Crawl4AI (предпочтительно) - для динамического контента
2. Jina Reader API (fallback) - бесплатный Markdown API
3. Direct HTML parsing (legacy) - BeautifulSoup
"""
import asyncio
import json
import re
import logging
import hashlib
from datetime import datetime, date
from bs4 import BeautifulSoup

from app.parsers.base import (
    ParsedEvent,
    ParserConfig,
    BaseParser,
    parse_russian_date,
    detect_event_type,
)
from app.parsers.ai_extractor import (
    AIEventExtractor,
    fetch_markdown_jina,
    CRAWL4AI_AVAILABLE,
)

logger = logging.getLogger(__name__)

# Конфигурация
YANDEX_AFISHA_CONFIG = ParserConfig(
    name="yandex_afisha",
    source="yandex",
    base_url="https://afisha.yandex.ru",
    timeout=30,
    max_retries=3,
    rate_limit_delay=1.0,
)

# Категории Яндекс Афиши
YANDEX_CATEGORIES = {
    "concert": "концерты",
    "theater": "спектакли",
    "exhibitions": "выставки",
    "cinema": "кино",
    "kids": "детям",
    "standup": "стендап",
}


_VENUE_RE = re.compile(
    r'(?:театр|филармония|музей|галерея|дворец|центр|ДК|библиотека|зал|клуб|арена|стадион|кинотеатр)'
    r'[^\n,]{0,60}',
    re.IGNORECASE,
)

_LOCATION_PREFIX_RE = re.compile(
    r'(?:место|площадка|где|адрес)[:\s—–-]+([^\n,]{3,80})',
    re.IGNORECASE,
)


def _strip_markdown(text: str) -> str:
    """Удалить markdown-разметку из текста."""
    text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)
    text = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    return text.strip()


def _clean_location(loc: str) -> str:
    """Удалить даты, маркеры и мусор из названия площадки."""
    loc = loc.split('•')[0].strip()
    loc = re.sub(
        r'\s*\d{1,2}\s+(?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)\w*.*$',
        '', loc, flags=re.IGNORECASE,
    )
    return loc.strip() or "Иркутск"


def _extract_location(text: str) -> str:
    """Извлечь название площадки из текстового блока."""
    clean = _strip_markdown(text)
    m = _LOCATION_PREFIX_RE.search(clean)
    if m:
        return _clean_location(m.group(1))[:100]
    m = _VENUE_RE.search(clean)
    if m:
        return _clean_location(m.group(0))[:100]
    return "Иркутск"


class YandexAfishaParser(BaseParser):
    """Парсер Яндекс Афиши для Иркутска."""
    
    def __init__(self, city: str = "irkutsk"):
        super().__init__(YANDEX_AFISHA_CONFIG)
        self.city = city
        self.base_events_url = f"{self.config.base_url}/{city}"
    
    async def fetch_events(
        self,
        categories: list[str] | None = None,
        days_ahead: int = 30,
        use_ai: bool = True
    ) -> list[ParsedEvent]:
        """
        Получить события с Яндекс Афиши.
        
        Args:
            categories: Список категорий (по умолчанию все)
            days_ahead: Количество дней вперёд (не используется напрямую)
            use_ai: Использовать AI extraction (Crawl4AI/Jina)
            
        Returns:
            Список ParsedEvent
        """
        all_events = []
        seen_ids = set()
        
        # URL для парсинга (актуальные на 2026)
        urls_to_parse = [
            f"{self.base_events_url}",  # Главная
            f"{self.base_events_url}/events",  # Все события
            f"{self.base_events_url}/theatre",  # Театр (рабочий URL)
        ]

        # Добавляем категории (только рабочие)
        if categories:
            for cat in categories:
                if cat in ["theatre", "events"]:
                    urls_to_parse.append(f"{self.base_events_url}/{cat}")
        else:
            # Рабочие категории
            for cat in ["events", "theatre"]:
                if f"{self.base_events_url}/{cat}" not in urls_to_parse:
                    urls_to_parse.append(f"{self.base_events_url}/{cat}")
        
        for url in urls_to_parse:
            self.logger.info(f"Парсинг: {url}")
            
            if use_ai:
                events = await self._fetch_events_ai(url)
            else:
                events = await self._fetch_events_html(url)
            
            for event in events:
                if event.id not in seen_ids:
                    all_events.append(event)
                    seen_ids.add(event.id)
            
            self.logger.info(f"Получено {len(events)} событий с {url}")
            
            # Rate limiting между запросами
            await asyncio.sleep(self.config.rate_limit_delay)
        
        self.log_stats()
        return all_events
    
    async def _fetch_events_ai(self, url: str) -> list[ParsedEvent]:
        """Извлечение через AI (Crawl4AI или Jina)."""
        events = []
        
        if CRAWL4AI_AVAILABLE:
            # Используем Crawl4AI
            try:
                async with AIEventExtractor(headless=True) as extractor:
                    markdown = await extractor.extract_markdown(url)
                    if markdown:
                        events = await self._parse_markdown(markdown)
            except Exception as e:
                self.logger.error(f"Ошибка Crawl4AI: {e}")
        
        if not events:
            # Fallback на Jina Reader
            self.logger.info("Используем Jina Reader fallback")
            markdown = await fetch_markdown_jina(url)
            if markdown:
                events = await self._parse_markdown(markdown)
        
        return events
    
    async def _parse_markdown(self, markdown: str) -> list[ParsedEvent]:
        """Парсинг Markdown в события."""
        events = []
        
        # Разбиваем на блоки по заголовкам или разделителям
        blocks = re.split(r'\n(?=#+\s|\*\*[^*]+\*\*\n)', markdown)
        
        for block in blocks:
            event = self._parse_event_block(block)
            if event:
                events.append(event)
        
        return events
    
    def _parse_event_block(self, block: str) -> ParsedEvent | None:
        """Парсинг одного блока события."""
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return None
        
        title = re.sub(r'^[#*\s]+', '', lines[0]).strip()
        title = re.sub(r'\*+$', '', title).strip()
        title = _strip_markdown(title)
        
        if len(title) < 3 or len(title) > 200:
            return None
        
        skip_patterns = [
            'меню', 'навигация', 'поиск', 'войти', 'главная',
            'афиша', 'билеты', 'корзина', 'яндекс', 'cookie',
            'уже в кино', 'источник', 'подробнее', 'сейчас выбирают',
            'доска объявлений', 'попробуйте выбрать', 'репертуар',
            'расписание', 'фильтр', 'каталог', 'показать ещё',
            'рекомендуем', 'подборк', 'все события',
        ]
        if any(p in title.lower() for p in skip_patterns):
            return None
        
        text = _strip_markdown('\n'.join(lines[1:]))
        
        # Дата
        date_match = re.search(
            r'(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)',
            text.lower()
        )
        event_date = parse_russian_date(date_match.group(0)) if date_match else str(date.today())
        
        # Время
        time_match = re.search(r'(\d{1,2}):(\d{2})', text)
        event_time = time_match.group(0) if time_match else None
        
        # Цена
        price_match = re.search(r'(?:от\s*)?(\d[\d\s]*)\s*(?:руб|₽|р\.?)', text)
        price = price_match.group(0).strip() if price_match else None
        price_min = None
        if price_match:
            price_num = re.sub(r'\s+', '', price_match.group(1))
            try:
                price_min = int(price_num)
            except ValueError:
                pass
        
        location = _extract_location(text)
        
        # URL
        url_match = re.search(r'https?://[^\s\)]+', block)
        url = url_match.group(0) if url_match else None
        
        # Описание
        description = text[:300].strip()
        
        event_id = self.generate_event_id(title, event_date, "yandex")
        event_type = detect_event_type(title, description)
        
        try:
            return ParsedEvent(
                id=event_id,
                title=title,
                description=description,
                date_start=event_date,
                time_start=event_time,
                event_type=event_type,
                location=location,
                price=price,
                price_min=price_min,
                source="yandex",
                url=url,
            )
        except Exception as e:
            self.logger.debug(f"Ошибка создания события: {e}")
            return None
    
    async def _fetch_events_html(self, url: str) -> list[ParsedEvent]:
        """Fallback: прямой HTML парсинг."""
        events = []
        
        html = await self.fetch_with_retry(url)
        if not html:
            return events
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Яндекс Афиша использует React, поэтому HTML парсинг ограничен
        # Ищем JSON-LD или data-атрибуты
        
        # JSON-LD schema.org
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'Event':
                    events.extend(self._parse_jsonld_event(data))
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get('@type') == 'Event':
                            events.extend(self._parse_jsonld_event(item))
            except json.JSONDecodeError:
                continue
        
        return events
    
    def _parse_jsonld_event(self, data: dict) -> list[ParsedEvent]:
        """Парсинг события из JSON-LD."""
        events = []
        
        try:
            title = data.get('name', '')
            if not title:
                return events
            
            # Дата
            start_date = data.get('startDate', '')
            if start_date:
                try:
                    dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    event_date = str(dt.date())
                    event_time = dt.strftime('%H:%M')
                except (ValueError, AttributeError, TypeError):
                    event_date = str(date.today())
                    event_time = None
            else:
                event_date = str(date.today())
                event_time = None
            
            # Место
            location_data = data.get('location', {})
            if isinstance(location_data, dict):
                location = location_data.get('name', 'Иркутск')
            else:
                location = "Иркутск"
            
            # Цена
            offers = data.get('offers', {})
            price_min = None
            price = None
            if isinstance(offers, dict):
                price_min = offers.get('lowPrice') or offers.get('price')
                if price_min:
                    price = f"от {price_min} руб"
            
            event_id = self.generate_event_id(title, event_date, "yandex")
            
            event = ParsedEvent(
                id=event_id,
                title=title,
                description=data.get('description', '')[:500] or None,
                date_start=event_date,
                time_start=event_time,
                event_type=detect_event_type(title),
                location=location,
                price=price,
                price_min=int(price_min) if price_min else None,
                source="yandex",
                url=data.get('url'),
                image_url=data.get('image'),
            )
            events.append(event)
            
        except Exception as e:
            self.logger.debug(f"Ошибка парсинга JSON-LD: {e}")
        
        return events


async def fetch_events_yandex(
    city: str = "irkutsk",
    categories: list[str] | None = None,
    use_ai: bool = True
) -> list[ParsedEvent]:
    """
    Получить события с Яндекс Афиши.

    Args:
        city: Город (slug)
        categories: Категории для парсинга
        use_ai: Использовать AI extraction

    Returns:
        Список ParsedEvent
    """
    async with YandexAfishaParser(city) as parser:
        return await parser.run_with_health(categories=categories, use_ai=use_ai)


# Тест
async def test_yandex_parser():
    """Тестирование парсера Яндекс Афиши."""
    print("=" * 50)
    print("Тест парсера Яндекс Афиши")
    print("=" * 50)
    
    events = await fetch_events_yandex(use_ai=True)
    
    print(f"\nВсего получено событий: {len(events)}")
    
    for event in events[:10]:
        print(f"\n- {event.title}")
        print(f"  Дата: {event.date_start} {event.time_start or ''}")
        print(f"  Место: {event.location}")
        print(f"  Цена: {event.price or 'не указана'}")
        print(f"  Тип: {event.event_type}")


if __name__ == "__main__":
    asyncio.run(test_yandex_parser())
