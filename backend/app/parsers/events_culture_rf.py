"""Парсер событий с Культура РФ (culture.ru).

Культура РФ - федеральный портал культурного наследия России.
Содержит афишу культурных событий: выставки, концерты, спектакли.

URL: https://www.culture.ru/afisha/irkutskaya-oblast-irkutsk
"""

import asyncio
import json
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
from app.parsers.ai_extractor import fetch_markdown_jina
from app.parsers.anti_detection import rate_limiter, response_cache

logger = logging.getLogger(__name__)

# Встроенное состояние Next.js: полный список событий приходит внутри HTML,
# отдельный запрос к API и рендер страницы не нужны.
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)


def _extract_address_from_jsonld(jsonld: dict) -> str | None:
    """Извлекает street address из JSON-LD location.address."""
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


_VENUE_KEYWORDS = re.compile(
    r'(музей|театр|дворец|филармония|библиотека|центр|галерея|ДК|клуб|зал)',
    re.IGNORECASE,
)

# Адреса в формате "г. Иркутск, ул. Карла Маркса, 1" / "Иркутск, Карла Маркса 5"
_ADDRESS_RE = re.compile(
    r'(?:г\.\s*)?(Иркутск|Ангарск|Шелехов|Усть-Илимск|Братск)[,\s]+'
    r'(?:ул\.|улица|пр-?т\.?|проспект|пер\.|переулок|б-р|бульвар)\s*'
    r'[А-ЯЁа-яё][А-ЯЁа-яё\s\.\-]{2,40}'
    r'(?:,?\s*д?\.?\s*\d{1,4}[А-Яа-я]?(?:/\d{1,3})?)?',
    re.IGNORECASE,
)


def _extract_address_from_markdown(text: str) -> str | None:
    """Best-effort извлечение адреса из markdown-блока.

    Args:
        text: Markdown context (несколько строк рядом с событием).

    Returns:
        Строка адреса или None.
    """
    if not text:
        return None
    m = _ADDRESS_RE.search(text)
    if m:
        addr = m.group(0).strip().rstrip(",.")
        # Чистим избыточные пробелы
        addr = re.sub(r"\s+", " ", addr)
        if 8 < len(addr) < 120:
            return addr
    return None


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
        
        # Встроенное состояние Next.js — обычный GET, без браузера и без Jina.
        html = await self.fetch_with_retry(url)
        if html:
            await rate_limiter.report_success(url)
            events = self._parse_next_data(html)
            self.logger.info(f"__NEXT_DATA__: {len(events)} событий")
        else:
            await rate_limiter.report_error(url)

        # Jina Reader — запасной путь на случай смены разметки. С прод-IP он
        # отдаёт 451 и закорачивается внутри fetch_markdown_jina.
        if not events:
            markdown = await fetch_markdown_jina(url)
            if markdown:
                response_cache.set(url, markdown)
                events = self._parse_markdown(markdown)
                self.logger.info(f"Jina Reader: {len(events)} событий")

        return events

    def _parse_next_data(self, html: str) -> list[ParsedEvent]:
        """Извлечь события из блока ``__NEXT_DATA__`` страницы афиши.

        Записи без разбираемой даты начала пропускаются. На 10.08.2026 листинг
        culture.ru не отдаёт её вовсе: ``date`` и ``seanceStartDate`` пусты у
        всех записей, заполнен только ``seanceEndDate``, а детальные страницы по
        ссылкам из собственной microdata отвечают 404. Подставлять дату
        окончания вместо даты начала нельзя — даты событий питают оценку
        событийного эффекта, и сдвинутая дата испортит её молча.
        """
        match = _NEXT_DATA_RE.search(html)
        if not match:
            self.logger.warning("Блок __NEXT_DATA__ не найден — разметка изменилась")
            return []
        try:
            items = (
                json.loads(match.group(1))["props"]["pageProps"]["events"]["items"]
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.warning(f"Не разобрать __NEXT_DATA__: {e}")
            return []

        events: list[ParsedEvent] = []
        skipped_no_date = 0
        for item in items:
            event = self._event_from_item(item)
            if event is None:
                skipped_no_date += 1
                continue
            events.append(event)

        if skipped_no_date:
            self.logger.warning(
                f"Пропущено {skipped_no_date} записей culture.ru без даты начала: "
                "источник отдаёт только дату окончания"
            )
        return events

    def _event_from_item(self, item: dict) -> ParsedEvent | None:
        """Собрать ParsedEvent из записи листинга; None — если нет даты начала."""
        title = (item.get("title") or "").strip()
        if len(title) < 3:
            return None

        raw_start = item.get("date") or item.get("seanceStartDate")
        date_start = str(raw_start)[:10] if raw_start else None
        if not date_start:
            return None

        microdata = {}
        if isinstance(item.get("microdata"), str):
            try:
                microdata = json.loads(item["microdata"])
            except json.JSONDecodeError:
                microdata = {}

        place = (item.get("places") or [{}])[0]
        price = item.get("price") or {}
        genre = (item.get("genres") or [{}])[0].get("title") or ""
        image = (microdata.get("image") or {}).get("url") if isinstance(microdata.get("image"), dict) else None

        raw_end = item.get("seanceEndDate")
        date_end = str(raw_end)[:10] if raw_end else None

        try:
            return ParsedEvent(  # pyright: ignore[reportCallIssue]
                id=self.generate_event_id(title, date_start, "culture_rf"),
                title=title,
                description=(microdata.get("text") or "").strip() or None,
                date_start=date_start,
                date_end=date_end if date_end and date_end != date_start else None,
                event_type=detect_event_type(title, genre),
                location=item.get("topPlaceTitle") or place.get("title") or "Иркутск",
                address=place.get("address"),
                price_min=price.get("min"),
                price_max=price.get("max"),
                source="culture_rf",
                url=microdata.get("url"),
                image_url=image,
            )
        except Exception as e:
            self.logger.debug(f"Запись culture.ru не прошла валидацию: {e}")
            return None

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

                # Контекст вокруг match для извлечения адреса
                ctx_start = max(0, match.start() - 200)
                ctx_end = min(len(markdown), match.end() + 400)
                context_block = markdown[ctx_start:ctx_end]
                address = _extract_address_from_markdown(context_block)
                
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
                    address=address,
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
        return await parser.run_with_health(location=location)
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
