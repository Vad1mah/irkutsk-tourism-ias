"""Парсер событий с Культура РФ (culture.ru).

Культура РФ - федеральный портал культурного наследия России.
Содержит афишу культурных событий: выставки, концерты, спектакли.

URL: https://www.culture.ru/afisha/irkutskaya-oblast-irkutsk
"""

import asyncio
import re
import logging
from datetime import date

from app.parsers.base import (
    ParsedEvent,
    ParserConfig,
    BaseParser,
    parse_russian_date,
    detect_event_type,
)
from app.parsers.ai_extractor import CRAWL4AI_AVAILABLE, fetch_markdown_jina
from app.parsers.anti_detection import rate_limiter, response_cache

logger = logging.getLogger(__name__)


_VENUE_KEYWORDS = re.compile(
    r'(музей|театр|дворец|филармония|библиотека|центр|галерея|ДК|клуб|зал)',
    re.IGNORECASE,
)


def _split_title_location(raw: str) -> tuple[str, str]:
    """Попытаться разделить 'Название Площадка' на title и location."""
    parts = raw.rsplit(" ", 1)
    if len(parts) == 2 and _VENUE_KEYWORDS.search(parts[1]):
        return parts[0].strip(), parts[1].strip()
    
    # Ищем паттерн вида "Название МузейЧего-то"
    m = _VENUE_KEYWORDS.search(raw)
    if m and m.start() > 5:
        return raw[:m.start()].strip(), raw[m.start():].strip()
    
    return raw, "Иркутская область"


class CultureRFParser(BaseParser):
    """Парсер событий с culture.ru."""

    def __init__(self):
        config = ParserConfig(
            name="culture_rf",
            source="culture.ru",
            base_url="https://www.culture.ru",
            timeout=30,
            max_retries=3,
        )
        super().__init__(config)

    async def fetch_events(
        self,
        location: str = "irkutskaya-oblast-irkutsk",
        max_pages: int = 3,
    ) -> list[ParsedEvent]:
        """
        Получить события с culture.ru.
        
        Args:
            location: Код региона
            max_pages: Максимум страниц для парсинга
            
        Returns:
            Список событий
        """
        events: list[ParsedEvent] = []
        url = f"{self.config.base_url}/afisha/{location}"
        self.logger.info(f"Парсинг: {url}")
        
        await rate_limiter.wait_for(url)
        
        cached = response_cache.get(url)
        if cached:
            self.logger.debug("Используем кэш")
            return self._parse_markdown(cached)
        
        # Crawl4AI — основной метод
        if CRAWL4AI_AVAILABLE:
            try:
                from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
                
                async with AsyncWebCrawler(verbose=False) as crawler:
                    config = CrawlerRunConfig(
                        wait_until="domcontentloaded",
                        page_timeout=30000,
                    )
                    result = await crawler.arun(url=url, config=config)
                    
                    if result.success:
                        await rate_limiter.report_success(url)
                        response_cache.set(url, result.markdown)
                        events = self._parse_markdown(result.markdown)
                        self.logger.info(f"Crawl4AI: {len(events)} событий")
                    else:
                        await rate_limiter.report_error(url)
                        self.logger.warning(f"Crawl4AI ошибка: {result.error_message}")
            except Exception as e:
                self.logger.warning(f"Crawl4AI недоступен: {e}")
        
        # Jina Reader — fallback
        if not events:
            self.logger.info("Используем Jina Reader fallback")
            try:
                markdown = await fetch_markdown_jina(url)
                if markdown:
                    response_cache.set(url, markdown)
                    events = self._parse_markdown(markdown)
                    self.logger.info(f"Jina Reader: {len(events)} событий")
            except Exception as e:
                self.logger.error(f"Jina Reader ошибка: {e}")
                await rate_limiter.report_error(url)
        
        return events

    def _parse_markdown(self, markdown: str) -> list[ParsedEvent]:
        """Парсинг Markdown с culture.ru."""
        events = []
        
        # Актуальный формат (2026):
        # [ 13 мар пт 18:00 от 550 руб. Спектакль «Дон Жуан сейчас» Театр ](url)
        # Также возможен формат с картинкой: [ ![](img) 13 мар ... ]
        pattern = re.compile(
            r'\[\s*(?:!\[[^\]]*\]\([^)]+\)\s*)?'
            r'(\d{1,2}\s+[а-яё]{3,8})\s+[а-яё]{2}\s+'
            r'(\d{1,2}:\d{2})\s*'
            r'от\s+(\d+)\s*руб\.?\s*'
            r'([^\]]+?)'
            r'\s*\]\(([^)]+)\)',
            re.IGNORECASE | re.DOTALL,
        )
        
        for match in pattern.finditer(markdown):
            try:
                date_str = match.group(1).strip()  # "16 февр"
                time_str = match.group(2).strip()  # "10:00"
                price_str = match.group(3).strip()  # "0"
                title_place = match.group(4).strip()  # "Название Место"
                url = match.group(5).strip()  # URL
                
                # Парсим дату
                date_match = re.search(r'(\d{1,2})\s+([а-яё]+)', date_str)
                if date_match:
                    day = date_match.group(1)
                    month_str = date_match.group(2)
                    month_map = {
                        'янв': 'января', 'фев': 'февраля', 'мар': 'марта',
                        'апр': 'апреля', 'май': 'мая', 'мая': 'мая',
                        'июн': 'июня', 'июл': 'июля', 'авг': 'августа',
                        'сен': 'сентября', 'окт': 'октября', 'ноя': 'ноября',
                        'дек': 'декабря',
                    }
                    full_month = month_map.get(month_str[:3], month_str)
                    event_date = parse_russian_date(f"{day} {full_month}")
                else:
                    event_date = str(date.today())
                
                event_time = time_str
                
                raw = re.sub(r'\s+', ' ', title_place).strip()
                title, location = _split_title_location(raw)
                
                skip_words = ['подробнее', 'показать', 'загрузить', 'пушкинская']
                if any(w in title.lower() for w in skip_words):
                    continue
                
                if len(title) < 5:
                    continue
                
                price_min = int(price_str) if price_str else None
                price = f"от {price_min} руб" if price_min else "Бесплатно"
                
                if not url.startswith('http'):
                    url = f"{self.config.base_url}{url}"
                
                event_id = self.generate_event_id(title, event_date, "culture_rf")
                
                event = ParsedEvent(
                    id=event_id,
                    title=title,
                    description=None,
                    date_start=event_date,
                    time_start=event_time,
                    event_type=detect_event_type(title),
                    location=location,
                    price=price,
                    price_min=price_min if price_min and price_min > 0 else None,
                    source="culture_rf",
                    url=url,
                )
                events.append(event)
                
            except Exception as e:
                self.logger.debug(f"Ошибка парсинга события: {e}")
                continue
        
        return events


async def fetch_events_culture_rf(
    location: str = "irkutskaya-oblast-irkutsk",
) -> list[ParsedEvent]:
    """Получить события с culture.ru."""
    parser = CultureRFParser()
    try:
        return await parser.fetch_events(location=location)
    finally:
        await parser._close_session()


# === Тест ===

if __name__ == "__main__":
    async def test():
        print("=" * 50)
        print("Тест парсера Культура РФ")
        print("=" * 50)
        
        events = await fetch_events_culture_rf()
        
        print(f"\nВсего получено событий: {len(events)}\n")
        
        for event in events[:10]:
            print(f"- {event.title}")
            print(f"  Дата: {event.date_start} {event.time_start or ''}")
            print(f"  Цена: {event.price}")
            print(f"  Тип: {event.event_type}")
            print()
    
    asyncio.run(test())
