"""Парсер событий с Kassir.ru.

Kassir.ru (irk.kassir.ru) - крупнейший билетный оператор:
- Концерты, спектакли, шоу
- Точные даты, время, цены
- Площадки Иркутска

Методы извлечения:
1. Crawl4AI - для JavaScript-рендеринга
2. Jina Reader - бесплатный Markdown API
3. Direct HTML - BeautifulSoup fallback
"""
import asyncio
import re
import json
import logging
import hashlib
from datetime import date
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
KASSIR_CONFIG = ParserConfig(
    name="kassir",
    source="kassir",
    base_url="https://irk.kassir.ru",
    timeout=30,
    max_retries=3,
    rate_limit_delay=1.5,
)

# Категории Kassir.ru
KASSIR_CATEGORIES = {
    "koncerty": "концерты",
    "teatr": "театр",
    "sport": "спорт",
    "detyam": "детям",
    "vystavki": "выставки",
    "standup": "стендап",
}


class KassirParser(BaseParser):
    """Парсер событий с Kassir.ru для Иркутска."""
    
    def __init__(self):
        super().__init__(KASSIR_CONFIG)
    
    async def fetch_events(
        self,
        categories: list[str] | None = None,
        use_ai: bool = True
    ) -> list[ParsedEvent]:
        """
        Получить события с Kassir.ru.
        
        Args:
            categories: Категории для парсинга
            use_ai: Использовать AI extraction
            
        Returns:
            Список ParsedEvent
        """
        all_events = []
        seen_ids = set()
        
        # URLs для парсинга
        urls_to_parse = [self.config.base_url]
        
        if categories:
            for cat in categories:
                if cat in KASSIR_CATEGORIES:
                    urls_to_parse.append(f"{self.config.base_url}/{cat}/")
        else:
            # Рабочие категории (актуальные на 2026)
            for cat in ["teatr", "sport", "vystavki", "standup"]:
                urls_to_parse.append(f"{self.config.base_url}/{cat}/")
        
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
            await asyncio.sleep(self.config.rate_limit_delay)
        
        self.log_stats()
        return all_events
    
    async def _fetch_events_ai(self, url: str) -> list[ParsedEvent]:
        """Извлечение через AI."""
        events = []
        
        if CRAWL4AI_AVAILABLE:
            try:
                async with AIEventExtractor(headless=True) as extractor:
                    markdown = await extractor.extract_markdown(url)
                    if markdown:
                        events = self._parse_kassir_markdown(markdown)
            except Exception as e:
                self.logger.error(f"Ошибка Crawl4AI: {e}")
        
        if not events:
            # Jina Reader fallback
            self.logger.info("Используем Jina Reader")
            markdown = await fetch_markdown_jina(url)
            if markdown:
                events = self._parse_kassir_markdown(markdown)
        
        return events
    
    def _parse_kassir_markdown(self, markdown: str) -> list[ParsedEvent]:
        """Парсинг Markdown с Kassir.ru."""
        events = []
        url_map = self._extract_urls_from_markdown(markdown)
        venue_map = self._extract_venues_from_markdown(markdown)
        
        # Паттерн 0: Crawl4AI формат (несколько вариантов)
        # Вариант A: ![Название](url) Название\n * дата\n * цена
        # Вариант B: ![Название](url)\n## Название\n * дата\n * цена
        
        # Общий паттерн - ищем ## Название или просто Название после картинки
        pattern0 = re.compile(
            r'!\[([А-Яа-яЁёA-Za-z][^\]]{2,50})\]\([^)]+\)\s*(?:##?\s*)?\1?\s*\n'
            r'\s*\*\s+(\d{1,2}[^\n]*(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)[^\n]*)\s*\n'
            r'\s*\*\s+(\d[\d\s]*)[—–-]\s*(\d[\d\s]*)',
            re.IGNORECASE
        )
        
        # Паттерн 0b: ## Название после картинки
        pattern0b = re.compile(
            r'!\[([А-Яа-яЁёA-Za-z][^\]]{2,50})\]\([^)]+\)\s*\n+##\s+([^\n]+)\s*\n'
            r'\s*\*\s+(\d{1,2}[^\n]*(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)[^\n]*)\s*\n'
            r'\s*\*\s+(\d[\d\s]*)[—–-]\s*(\d[\d\s]*)',
            re.IGNORECASE
        )
        
        for match in pattern0.finditer(markdown):
            title = match.group(1).strip()
            date_str = match.group(2).strip()
            price_min_str = match.group(3).strip()
            price_max_str = match.group(4).strip()
            
            skip_words = ['афиша', 'билеты', 'kassir', 'логотип', 'меню', 'реклама']
            if any(w in title.lower() for w in skip_words):
                continue
            
            if len(title) < 3:
                continue
            
            event_date = parse_russian_date(date_str)
            if not event_date:
                event_date = str(date.today())
            
            try:
                price_min = int(re.sub(r'\s+', '', price_min_str))
                price_max = int(re.sub(r'\s+', '', price_max_str))
                price = f"{price_min} — {price_max} руб"
            except ValueError:
                price_min = None
                price_max = None
                price = None
            
            event_id = self.generate_event_id(title, event_date, "kassir")
            
            try:
                event = ParsedEvent(
                    id=event_id,
                    title=title,
                    description=None,
                    date_start=event_date,
                    event_type=detect_event_type(title),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    source="kassir",
                    url=url_map.get(title.lower()),
                )
                events.append(event)
            except Exception as e:
                self.logger.debug(f"Ошибка Crawl4AI паттерн: {e}")
        
        # Паттерн 0b: ## Название на отдельной строке
        for match in pattern0b.finditer(markdown):
            img_title = match.group(1).strip()
            title = match.group(2).strip()
            date_str = match.group(3).strip()
            price_min_str = match.group(4).strip()
            price_max_str = match.group(5).strip()
            
            skip_words = ['афиша', 'билеты', 'kassir', 'логотип', 'меню', 'реклама']
            if any(w in title.lower() for w in skip_words):
                continue
            
            if len(title) < 3:
                continue
            
            event_date = parse_russian_date(date_str)
            if not event_date:
                event_date = str(date.today())
            
            # Проверяем дубликаты
            event_id = self.generate_event_id(title, event_date, "kassir")
            if any(e.id == event_id for e in events):
                continue
            
            try:
                price_min = int(re.sub(r'\s+', '', price_min_str))
                price_max = int(re.sub(r'\s+', '', price_max_str))
                price = f"{price_min} — {price_max} руб"
            except ValueError:
                price_min = None
                price_max = None
                price = None
            
            try:
                event = ParsedEvent(
                    id=event_id,
                    title=title,
                    description=None,
                    date_start=event_date,
                    event_type=detect_event_type(title),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    source="kassir",
                    url=url_map.get(title.lower()),
                )
                events.append(event)
            except Exception as e:
                self.logger.debug(f"Ошибка Crawl4AI паттерн 0b: {e}")
        
        # Паттерн 1: Заголовок с подчёркиванием (формат Kassir через Jina Reader)
        # Название
        # ---------
        # *    27,28 февраля
        # *    6400 — 11900
        pattern1 = re.compile(
            r'([А-Яа-яЁёA-Za-z][^\n\[\]]{2,50})\n-+\n+'
            r'\*\s+(\d{1,2}[^\n]*(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)[^\n]*)\s*\n'
            r'\*\s+(\d[\d\s]*)[—–-]\s*(\d[\d\s]*)',
            re.IGNORECASE
        )
        
        for match in pattern1.finditer(markdown):
            title = match.group(1).strip()
            date_str = match.group(2).strip()
            price_min_str = match.group(3).strip()
            price_max_str = match.group(4).strip()
            
            # Пропускаем служебные
            skip_words = ['афиша', 'билеты', 'kassir', 'логотип', 'меню', 'реклама']
            if any(w in title.lower() for w in skip_words):
                continue
            
            if len(title) < 3:
                continue
            
            event_date = parse_russian_date(date_str)
            if not event_date:
                event_date = str(date.today())
            
            try:
                price_min = int(re.sub(r'\s+', '', price_min_str))
                price_max = int(re.sub(r'\s+', '', price_max_str))
                price = f"{price_min} — {price_max} руб"
            except ValueError:
                price_min = None
                price_max = None
                price = None
            
            event_id = self.generate_event_id(title, event_date, "kassir")
            
            try:
                event = ParsedEvent(
                    id=event_id,
                    title=title,
                    description=None,
                    date_start=event_date,
                    event_type=detect_event_type(title),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    source="kassir",
                    url=url_map.get(title.lower()),
                )
                events.append(event)
            except Exception as e:
                self.logger.debug(f"Ошибка создания события: {e}")
        
        # Паттерн 2: Простой формат "Название\n* дата\n* цена"
        pattern2 = re.compile(
            r'\[Image[^\]]*\]\s*([А-Яа-яЁёA-Za-z][^\n\[]{2,50})\n'
            r'(?:-+\n)?'
            r'\*\s+(\d{1,2}[^\n]*(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря|марта)[^\n]*)\n'
            r'\*\s+(\d[\d\s]*[—–-]\s*\d[\d\s]*)',
            re.IGNORECASE
        )
        
        for match in pattern2.finditer(markdown):
            title = match.group(1).strip()
            date_str = match.group(2).strip()
            price_str = match.group(3).strip()
            
            skip_words = ['афиша', 'билеты', 'kassir', 'логотип', 'меню']
            if any(w in title.lower() for w in skip_words):
                continue
            
            if len(title) < 3:
                continue
            
            # Проверяем, не добавили ли уже
            event_date = parse_russian_date(date_str) or str(date.today())
            event_id = self.generate_event_id(title, event_date, "kassir")
            
            if any(e.id == event_id for e in events):
                continue
            
            price_match = re.search(r'(\d[\d\s]*)[—–-](\d[\d\s]*)', price_str)
            if price_match:
                try:
                    price_min = int(re.sub(r'\s+', '', price_match.group(1)))
                    price = price_str + " руб"
                except ValueError:
                    price_min = None
                    price = price_str
            else:
                price_min = None
                price = price_str
            
            try:
                event = ParsedEvent(
                    id=event_id,
                    title=title,
                    description=None,
                    date_start=event_date,
                    event_type=detect_event_type(title),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    source="kassir",
                    url=url_map.get(title.lower()),
                )
                events.append(event)
            except Exception as e:
                self.logger.debug(f"Ошибка: {e}")
        
        return events
    
    @staticmethod
    def _extract_urls_from_markdown(markdown: str) -> dict[str, str]:
        """Извлечь маппинг title→url из Markdown ссылок (без CDN-картинок)."""
        url_map: dict[str, str] = {}
        for m in re.finditer(r'\[([^\]]{3,60})\]\((https?://[^)]+)\)', markdown):
            title = m.group(1).strip().lower()
            href = m.group(2).strip()
            if ("kassir.ru" in href
                    and "cdn.kassir.ru" not in href
                    and title not in url_map):
                url_map[title] = href
        return url_map

    @staticmethod
    def _extract_venues_from_markdown(markdown: str) -> dict[str, str]:
        """Извлечь маппинг title→venue из контекста Markdown."""
        venue_map: dict[str, str] = {}
        venue_pattern = re.compile(
            r'(?:площадка|место|где)\s*[:\-–]\s*(.+)',
            re.IGNORECASE,
        )
        lines = markdown.split("\n")
        for i, line in enumerate(lines):
            vm = venue_pattern.search(line)
            if vm:
                venue = vm.group(1).strip()
                for j in range(max(0, i - 5), i):
                    prev = lines[j].strip()
                    if prev and len(prev) > 3:
                        venue_map[prev.lower().lstrip("#").strip()] = venue
        return venue_map

    async def _fetch_events_html(self, url: str) -> list[ParsedEvent]:
        """Fallback: прямой HTML парсинг."""
        events = []

        html = await self.fetch_with_retry(url)
        if not html:
            return events

        soup = BeautifulSoup(html, 'html.parser')

        # Сначала пробуем JSON-LD (самый надёжный источник)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if '@graph' in data:
                    for item in data['@graph']:
                        if item.get('@type') == 'Event':
                            event = self._parse_jsonld_event(item)
                            if event:
                                events.append(event)
                elif data.get('@type') == 'Event':
                    event = self._parse_jsonld_event(data)
                    if event:
                        events.append(event)
            except (json.JSONDecodeError, TypeError):
                continue

        if events:
            self.logger.info(f"JSON-LD: найдено {len(events)} событий")
            return events

        # Fallback: ищем карточки событий
        event_selectors = [
            '.event-card',
            '.event-item',
            '.show-item',
            'article[data-event]',
            '.poster-card',
        ]

        event_cards = []
        for selector in event_selectors:
            event_cards = soup.select(selector)
            if event_cards:
                break

        if not event_cards:
            event_cards = soup.find_all('div', class_=re.compile(r'event|show|poster'))

        for card in event_cards[:50]:
            event = self._parse_event_card(card)
            if event:
                events.append(event)

        return events

    def _parse_jsonld_event(self, data: dict) -> ParsedEvent | None:
        """Парсинг события из JSON-LD."""
        try:
            name = data.get('name', '')
            if not name or len(name) < 3:
                return None

            # Дата
            start_date = data.get('startDate', '')
            if start_date:
                # ISO format: 2026-03-15T19:00:00+08:00
                start_date = start_date[:10]

            # Локация
            location = data.get('location', {})
            location_name = ''
            if isinstance(location, dict):
                location_name = location.get('name', 'Иркутск')
            else:
                location_name = 'Иркутск'

            # URL
            event_url = data.get('url', '')

            # ID из URL или хэш
            if event_url:
                event_id = f"kassir_{hashlib.md5(event_url.encode()).hexdigest()[:10]}"
            else:
                event_id = f"kassir_{hashlib.md5(name.encode()).hexdigest()[:10]}"

            return ParsedEvent(
                id=event_id,
                title=name,
                description=data.get('description') or None,
                date_start=start_date,
                event_type=detect_event_type(name, data.get('description', '')),
                location=location_name,
                source="kassir",
                url=event_url,
            )
        except Exception as e:
            self.logger.debug(f"JSON-LD parse error: {e}")
            return None
    
    def _parse_event_card(self, card) -> ParsedEvent | None:
        """Парсинг карточки события."""
        try:
            # Название
            title_elem = card.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name'))
            if not title_elem:
                title_elem = card.find(['h2', 'h3', 'h4'])
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            if len(title) < 5:
                return None
            
            # Дата
            date_elem = card.find(class_=re.compile(r'date|time'))
            if not date_elem:
                date_elem = card.find('time')
            
            date_text = date_elem.get_text(strip=True) if date_elem else ""
            event_date = parse_russian_date(date_text) or str(date.today())
            
            # Цена
            price_elem = card.find(class_=re.compile(r'price|cost'))
            price_text = price_elem.get_text(strip=True) if price_elem else ""
            
            price = None
            price_min = None
            price_match = re.search(r'(\d[\d\s]*)', price_text)
            if price_match:
                price = price_text
                try:
                    price_min = int(re.sub(r'\s+', '', price_match.group(1)))
                except ValueError:
                    pass
            
            # Место
            venue_elem = card.find(class_=re.compile(r'venue|place|location'))
            location = venue_elem.get_text(strip=True) if venue_elem else "Иркутск"
            
            # URL
            link = card.find('a', href=True)
            url = link['href'] if link else None
            if url and not url.startswith('http'):
                url = f"{self.config.base_url}{url}"
            
            # Картинка
            img = card.find('img', src=True)
            image_url = img['src'] if img else None
            if image_url and not image_url.startswith('http'):
                image_url = f"{self.config.base_url}{image_url}"
            
            event_id = self.generate_event_id(title, event_date, "kassir")
            
            return ParsedEvent(
                id=event_id,
                title=title,
                description=None,
                date_start=event_date,
                event_type=detect_event_type(title),
                location=location,
                price=price,
                price_min=price_min,
                source="kassir",
                url=url,
                image_url=image_url,
            )
            
        except Exception as e:
            self.logger.debug(f"Ошибка парсинга карточки: {e}")
            return None


async def fetch_events_kassir(
    categories: list[str] | None = None,
    use_ai: bool = True
) -> list[ParsedEvent]:
    """
    Получить события с Kassir.ru.
    
    Args:
        categories: Категории для парсинга
        use_ai: Использовать AI extraction
        
    Returns:
        Список ParsedEvent
    """
    async with KassirParser() as parser:
        return await parser.fetch_events(categories=categories, use_ai=use_ai)


# Тест
async def test_kassir_parser():
    """Тестирование парсера Kassir.ru."""
    print("=" * 50)
    print("Тест парсера Kassir.ru")
    print("=" * 50)
    
    events = await fetch_events_kassir(use_ai=True)
    
    print(f"\nВсего получено событий: {len(events)}")
    
    for event in events[:10]:
        print(f"\n- {event.title}")
        print(f"  Дата: {event.date_start}")
        print(f"  Цена: {event.price or 'не указана'}")
        print(f"  Тип: {event.event_type}")


if __name__ == "__main__":
    asyncio.run(test_kassir_parser())
