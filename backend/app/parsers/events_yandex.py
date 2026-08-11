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
from datetime import datetime, date, time as _time
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


def parse_yandex_jsonld_event(jsonld: dict, source_url: str) -> dict:
    """Парсит одно событие из JSON-LD ответа afisha.yandex.ru.

    Args:
        jsonld: Словарь из тега <script type="application/ld+json">.
        source_url: URL страницы-источника.

    Returns:
        dict с ключами: title, description, image_url, age_restriction,
        time_start, url, date_start, location, price_min, price.
    """
    name = (jsonld.get("name") or "").strip()

    # Дата и время из startDate
    start_raw = jsonld.get("startDate") or ""
    event_date: str = str(date.today())
    time_start: _time | None = None
    if start_raw:
        try:
            dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            event_date = str(dt.date())
            time_start = dt.time()
        except (ValueError, TypeError):
            pass

    # Дата окончания (для многодневных событий)
    end_raw = jsonld.get("endDate") or ""
    date_end: str | None = None
    if end_raw:
        try:
            dt_end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            date_end_value = str(dt_end.date())
            # Не сохраняем endDate, если он совпадает со startDate
            if date_end_value != event_date:
                date_end = date_end_value
        except (ValueError, TypeError):
            pass

    # Описание до 2000 символов
    desc_raw = (jsonld.get("description") or "").strip()
    description: str | None = desc_raw[:2000] if desc_raw else None

    # Изображение
    image_raw = jsonld.get("image")
    image_url: str | None = image_raw if isinstance(image_raw, str) else None

    # age_restriction: "12-99" → "12+", "0-99" → None
    age_raw: str = jsonld.get("typicalAgeRange") or ""
    age_restriction: str | None = None
    if isinstance(age_raw, str) and "-" in age_raw:
        try:
            min_age = int(age_raw.split("-")[0])
            if min_age > 0:
                age_restriction = f"{min_age}+"
        except ValueError:
            pass

    # Место и адрес
    location_data = jsonld.get("location", {})
    address: str | None = None
    if isinstance(location_data, dict):
        location = location_data.get("name") or "Иркутск"
        addr_raw = location_data.get("address")
        if isinstance(addr_raw, dict):
            street = addr_raw.get("streetAddress") or addr_raw.get("addressLocality")
            if street:
                address = str(street).strip() or None
        elif isinstance(addr_raw, str) and addr_raw.strip():
            address = addr_raw.strip()
    else:
        location = "Иркутск"

    # Цена (lowPrice / highPrice / price)
    offers = jsonld.get("offers", {})
    price_min: int | None = None
    price_max: int | None = None
    price: str | None = None
    if isinstance(offers, dict):
        raw_price = offers.get("lowPrice") or offers.get("price")
        if raw_price is not None:
            try:
                price_min = int(float(raw_price))
            except (ValueError, TypeError):
                pass
        raw_high = offers.get("highPrice") or offers.get("maxPrice")  # noqa: dup
        if raw_high is not None:
            try:
                price_max = int(float(raw_high))
            except (ValueError, TypeError):
                pass
        if price_min is not None and price_max is not None and price_max > price_min:
            price = f"{price_min} — {price_max} руб"
        elif price_min is not None:
            price = f"от {price_min} руб"

    return {
        "title": name,
        "description": description,
        "image_url": image_url,
        "age_restriction": age_restriction,
        "time_start": time_start,
        "url": source_url or jsonld.get("url"),
        "date_start": event_date,
        "date_end": date_end,
        "location": location,
        "address": address,
        "price_min": price_min,
        "price_max": price_max,
        "price": price,
    }


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
        use_ai: bool = True,
        **kwargs,
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

        # /events — единственная страница, где Яндекс server-renders JSON-LD со
        # списком событий (ItemList). Категорийные страницы (/concert, /theatre,
        # /standup) рендерят список через JS и JSON-LD не содержат, а markdown-
        # эвристика на них путает пары title↔url (карусельные ссылки). Поэтому
        # полагаемся на агрегатор /events с корректными schema.org-данными.
        urls_to_parse = [f"{self.base_events_url}/events"]

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
        """Извлечение событий. Приоритет — JSON-LD из сырого HTML.

        JSON-LD даёт пару title↔url из одного schema.org-узла (корректно) и
        работает по обычному aiohttp без браузера — значит парсер живёт и в
        прод-контейнере. Markdown-эвристика (Crawl4AI/Jina) оставлена только как
        аварийный fallback для страниц без JSON-LD.
        """
        # 1) JSON-LD из сырого HTML (без браузера)
        html = await self.fetch_with_retry(url)
        if html:
            events = self._extract_jsonld_events(html)
            if events:
                return events

        # 2) Fallback: markdown-эвристика (Crawl4AI → Jina)
        events = []
        if CRAWL4AI_AVAILABLE:
            try:
                async with AIEventExtractor(headless=True) as extractor:
                    markdown = await extractor.extract_markdown(url)
                    if markdown:
                        events = await self._parse_markdown(markdown)
            except Exception as e:
                self.logger.error(f"Ошибка Crawl4AI: {e}")

        if not events:
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
        description = text[:2000].strip()
        
        if not event_date:
            return None
        event_id = self.generate_event_id(title, event_date, "yandex")
        event_type = detect_event_type(title, description)

        try:
            return ParsedEvent(  # pyright: ignore[reportCallIssue]
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
        """Прямой HTML-парсинг через JSON-LD (без браузера)."""
        html = await self.fetch_with_retry(url)
        return self._extract_jsonld_events(html or "")

    def _extract_jsonld_events(self, html: str) -> list[ParsedEvent]:
        """События из JSON-LD (`<script type="application/ld+json">`).

        name и url приходят из одного schema.org-узла, поэтому пара title↔url
        гарантирована — в отличие от markdown-эвристики, которая брала «первый
        url в блоке» и цепляла карусельные/соседние ссылки. Яндекс отдаёт
        ItemList событий на странице /events прямо в HTML, браузер не нужен.
        """
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        events: list[ParsedEvent] = []
        seen: set[str] = set()
        for script in soup.find_all('script', type='application/ld+json'):
            raw = script.string
            if not raw:
                continue
            try:
                data = json.loads(str(raw))
            except json.JSONDecodeError:
                continue
            for node in self._iter_jsonld_events(data):
                for event in self._parse_jsonld_event(node):
                    if event.id not in seen:
                        seen.add(event.id)
                        events.append(event)
        return events

    @staticmethod
    def _iter_jsonld_events(data):
        """Рекурсивно обойти JSON-LD, выдавая dict-узлы со схемой *Event.

        Поддерживает любую вложенность (ItemList → ListItem → item, @graph и т. п.).
        Узел-Event не разворачивается дальше — его location/offers не считаются
        отдельными событиями.
        """
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                raw_type = node.get('@type')
                is_event = (
                    (isinstance(raw_type, str) and 'Event' in raw_type)
                    or (isinstance(raw_type, list)
                        and any(isinstance(x, str) and 'Event' in x for x in raw_type))
                )
                if is_event:
                    yield node
                else:
                    stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    
    def _parse_jsonld_event(self, data: dict) -> list[ParsedEvent]:
        """Парсинг события из JSON-LD."""
        events = []

        try:
            title = data.get("name", "")
            if not title:
                return events

            fields = parse_yandex_jsonld_event(data, source_url=data.get("url") or "")
            event_id = self.generate_event_id(fields["title"], fields["date_start"], "yandex")

            # JSON-LD @type может быть строкой или списком; берём первый "Event"-подтип
            raw_type = data.get("@type")
            jsonld_type: str | None = None
            if isinstance(raw_type, list):
                for t in raw_type:
                    if isinstance(t, str) and "Event" in t:
                        jsonld_type = t
                        break
                if jsonld_type is None and raw_type:
                    jsonld_type = str(raw_type[0]) if raw_type[0] else None
            elif isinstance(raw_type, str):
                jsonld_type = raw_type

            time_start = fields["time_start"]
            # ParsedEvent.time_start ожидает str | None
            time_start_str: str | None = None
            if isinstance(time_start, _time):
                time_start_str = time_start.strftime("%H:%M")
            elif isinstance(time_start, str):
                time_start_str = time_start

            event = ParsedEvent(  # pyright: ignore[reportCallIssue]
                id=event_id,
                title=fields["title"],
                description=fields["description"],
                date_start=fields["date_start"],
                time_start=time_start_str,
                event_type=detect_event_type(
                    fields["title"],
                    fields.get("description") or "",
                    jsonld_type=jsonld_type,
                ),
                location=fields["location"],
                address=fields.get("address"),
                price=fields["price"],
                price_min=fields["price_min"],
                price_max=fields.get("price_max"),
                age_restriction=fields["age_restriction"],
                source="yandex",
                url=fields["url"] or None,
                image_url=fields["image_url"],
                date_end=fields.get("date_end"),
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
