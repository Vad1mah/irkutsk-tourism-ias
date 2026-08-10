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

def _extract_address_from_jsonld(jsonld: dict) -> str | None:
    """Извлекает street address из JSON-LD location.address.

    Поддерживает 2 формата: PostalAddress dict и plain string.

    Args:
        jsonld: Словарь JSON-LD события.

    Returns:
        Строка адреса или None.
    """
    loc = jsonld.get("location")
    if not isinstance(loc, dict):
        return None
    addr = loc.get("address")
    if isinstance(addr, str):
        return addr.strip() or None
    if isinstance(addr, dict):
        street = addr.get("streetAddress") or addr.get("addressLocality")
        if street:
            return str(street).strip() or None
    return None


def _extract_full_description(jsonld: dict) -> str | None:
    """Возвращает description из JSON-LD, обрезанный до 2000 символов.

    Args:
        jsonld: Словарь JSON-LD события.

    Returns:
        Строка описания (до 2000 chars) или None.
    """
    desc = jsonld.get("description") or ""
    desc = desc.strip()
    return desc[:2000] if desc else None


_AGE_RE = re.compile(r"\b(\d{1,2})\s*\+")


def _extract_age_from_text(text: str | None) -> str | None:
    """Извлекает возрастное ограничение вида '16+' / '18+' из текста.

    Args:
        text: Произвольный текст (title/description/markdown context).

    Returns:
        Строка вида ``"NN+"`` или None.
    """
    if not text:
        return None
    m = _AGE_RE.search(text)
    if not m:
        return None
    try:
        age = int(m.group(1))
        if 0 < age <= 21:
            return f"{age}+"
    except ValueError:
        pass
    return None


# Markdown-мусор, который точно не относится к описанию события
_MD_NOISE_LINES = re.compile(
    r"^(?:афиша|билеты|kassir|логотип|меню|реклама|подробнее|купить билет"
    r"|показать ещё|показать еще)\b",
    re.IGNORECASE,
)


def _description_from_markdown_context(
    markdown: str,
    match_end: int,
    max_lookahead: int = 25,
) -> str | None:
    """Извлекает текст описания из Markdown после блока с датой/ценой.

    Берёт строки после конца совпадения паттерна до следующего разделителя
    (картинка ![…](…), заголовок ##, начало нового списка с датой).
    Чистит пустые/шумовые строки и склеивает в один параграф,
    пропуская через _extract_full_description для единого формата.

    Args:
        markdown: Полный Markdown-текст страницы.
        match_end: Индекс конца совпадения regex'а в markdown.
        max_lookahead: Максимум строк вперёд для сбора описания.

    Returns:
        Строка описания (до 2000 chars) или None.
    """
    tail = markdown[match_end:]
    lines = tail.split("\n")
    chunks: list[str] = []
    for raw in lines[: max_lookahead + 5]:
        s = raw.strip()
        if not s:
            if chunks:
                continue
            else:
                continue
        # Граница следующего события / следующей секции
        if s.startswith("![") or s.startswith("##") or s.startswith("---"):
            break
        # Bullet с датой/ценой — это уже следующее событие
        if s.startswith("*") and re.search(
            r"\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|"
            r"августа|сентября|октября|ноября|декабря)",
            s.lower(),
        ):
            break
        if _MD_NOISE_LINES.match(s):
            continue
        # Markdown-bullet "* …" — оставляем содержимое после маркера
        cleaned = re.sub(r"^\*\s+", "", s)
        # Markdown-ссылки и картинки внутри строки удаляем
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", cleaned)
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = cleaned.strip()
        if not cleaned:
            continue
        chunks.append(cleaned)
        if len(chunks) >= max_lookahead:
            break
    if not chunks:
        return None
    text = " ".join(chunks)
    return _extract_full_description({"description": text})


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
        use_ai: bool = True,
        **kwargs,
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
            
            # JSON-LD из обычного HTML — самый дешёвый и надёжный источник:
            # один GET без браузера и без Jina. AI-путь остаётся запасным.
            events = await self._fetch_events_html(url)
            if not events and use_ai:
                events = await self._fetch_events_ai(url)

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
            description = _description_from_markdown_context(markdown, match.end())
            age_restriction = _extract_age_from_text(description) or _extract_age_from_text(title)

            try:
                event = ParsedEvent(  # pyright: ignore[reportCallIssue]
                    id=event_id,
                    title=title,
                    description=description,
                    date_start=event_date,
                    event_type=detect_event_type(title, description or ""),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    price_max=price_max,
                    age_restriction=age_restriction,
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

            description = _description_from_markdown_context(markdown, match.end())
            age_restriction = _extract_age_from_text(description) or _extract_age_from_text(title)

            try:
                event = ParsedEvent(  # pyright: ignore[reportCallIssue]
                    id=event_id,
                    title=title,
                    description=description,
                    date_start=event_date,
                    event_type=detect_event_type(title, description or ""),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    price_max=price_max,
                    age_restriction=age_restriction,
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
            description = _description_from_markdown_context(markdown, match.end())
            age_restriction = _extract_age_from_text(description) or _extract_age_from_text(title)

            try:
                event = ParsedEvent(  # pyright: ignore[reportCallIssue]
                    id=event_id,
                    title=title,
                    description=description,
                    date_start=event_date,
                    event_type=detect_event_type(title, description or ""),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    price_max=price_max,
                    age_restriction=age_restriction,
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
            
            description = _description_from_markdown_context(markdown, match.end())
            age_restriction = _extract_age_from_text(description) or _extract_age_from_text(title)

            try:
                event = ParsedEvent(  # pyright: ignore[reportCallIssue]
                    id=event_id,
                    title=title,
                    description=description,
                    date_start=event_date,
                    event_type=detect_event_type(title, description or ""),
                    location=venue_map.get(title.lower(), "Иркутск"),
                    price=price,
                    price_min=price_min,
                    age_restriction=age_restriction,
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
                if not script.string:
                    continue
                data = json.loads(str(script.string))
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

            # Дата окончания
            end_raw = data.get('endDate', '')
            date_end: str | None = None
            if end_raw:
                end_date = end_raw[:10]
                if end_date and end_date != start_date:
                    date_end = end_date

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

            description_text = _extract_full_description(data) or ""

            # Цена min/max
            offers = data.get("offers", {})
            price_min: int | None = None
            price_max: int | None = None
            price: str | None = None
            if isinstance(offers, dict):
                raw_low = offers.get("lowPrice") or offers.get("price")
                if raw_low is not None:
                    try:
                        price_min = int(float(raw_low))
                    except (ValueError, TypeError):
                        pass
                raw_high = offers.get("highPrice") or offers.get("maxPrice")
                if raw_high is not None:
                    try:
                        price_max = int(float(raw_high))
                    except (ValueError, TypeError):
                        pass
                if price_min is not None and price_max is not None and price_max > price_min:
                    price = f"{price_min} — {price_max} руб"
                elif price_min is not None:
                    price = f"от {price_min} руб"

            # Возрастное ограничение
            age_restriction: str | None = None
            age_raw = data.get("typicalAgeRange") or ""
            if isinstance(age_raw, str) and "-" in age_raw:
                try:
                    min_age = int(age_raw.split("-")[0])
                    if min_age > 0:
                        age_restriction = f"{min_age}+"
                except ValueError:
                    pass
            if age_restriction is None and description_text:
                m_age = re.search(r"\b(\d{1,2})\s*\+", description_text)
                if m_age:
                    age_restriction = f"{m_age.group(1)}+"

            return ParsedEvent(  # pyright: ignore[reportCallIssue]
                id=event_id,
                title=name,
                description=description_text or None,
                date_start=start_date,
                date_end=date_end,
                event_type=detect_event_type(
                    name,
                    data.get('description', '') or "",
                    jsonld_type=data.get('@type'),
                ),
                location=location_name,
                address=_extract_address_from_jsonld(data),
                price=price,
                price_min=price_min,
                price_max=price_max,
                age_restriction=age_restriction,
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
            
            return ParsedEvent(  # pyright: ignore[reportCallIssue]
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
        return await parser.run_with_health(categories=categories, use_ai=use_ai)


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
