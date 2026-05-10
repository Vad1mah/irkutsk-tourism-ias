"""Парсер событий с irk.ru/afisha."""
import logging
import aiohttp
from bs4 import BeautifulSoup
from datetime import date, time
from typing import Any
import re
import hashlib

from app.config import settings
from app.parsers.base import detect_event_type

logger = logging.getLogger(__name__)

_IRK_AFISHA_URL = "https://irk.ru/afisha/"


async def _parse_native_html(days_ahead: int = 30) -> list[dict[str, Any]]:
    """Нативный HTML-парсер irk.ru/afisha.

    Args:
        days_ahead: Не используется, парсим главную страницу афиши.

    Returns:
        Список словарей с данными о событиях.
    """
    url = settings.parser_irk_url
    events: list[dict[str, Any]] = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

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
                logger.warning("irk.ru вернул статус: %s", response.status)

    return events


async def _parse_via_crawl4ai(days_ahead: int = 30) -> list[dict[str, Any]]:
    """Crawl4AI/Jina-fallback когда нативный HTML-парсер не даёт результатов.

    Использует extract_events_simple из ai_extractor (Jina Reader + regex),
    а при наличии Crawl4AI — AIEventExtractor с полноценным рендерингом JS.

    Args:
        days_ahead: Не используется, зарезервирован для будущей фильтрации.

    Returns:
        Список словарей с данными о событиях (формат совместим с нативным парсером).
    """
    try:
        from app.parsers.ai_extractor import extract_events_simple, CRAWL4AI_AVAILABLE

        if CRAWL4AI_AVAILABLE:
            from app.parsers.ai_extractor import AIEventExtractor
            async with AIEventExtractor(headless=True) as extractor:
                markdown = await extractor.extract_markdown(_IRK_AFISHA_URL)
                if markdown:
                    parsed_events = await extractor.extract_events_from_markdown(
                        markdown, "irk"
                    )
                else:
                    parsed_events = []
        else:
            parsed_events = await extract_events_simple(_IRK_AFISHA_URL, "irk")

        # Конвертируем ParsedEvent → dict (формат, совместимый с нативным парсером)
        result: list[dict[str, Any]] = []
        for pe in parsed_events:
            if hasattr(pe, "model_dump"):
                d = pe.model_dump()
            else:
                # На случай если вернули plain dict
                d = dict(pe) if not isinstance(pe, dict) else pe
            result.append(d)
        return result

    except Exception as exc:
        logger.warning("events_irk Crawl4AI fallback failed: %s", exc)
        return []


async def fetch_events_irk(days_ahead: int = 30) -> list[dict[str, Any]]:
    """Получить список событий с irk.ru/afisha.

    Сначала пробует нативный HTML-парсер. При исключении или пустом результате
    переключается на Crawl4AI/Jina fallback для устойчивости к изменениям вёрстки.

    Args:
        days_ahead: Не используется, парсим главную страницу афиши.

    Returns:
        Список словарей с данными о событиях.
    """
    try:
        events = await _parse_native_html(days_ahead)
        if events:
            return events
        logger.info(
            "events_irk: нативный парсер вернул 0 событий — пробуем Crawl4AI fallback"
        )
    except Exception as exc:
        logger.warning(
            "events_irk: нативный парсер упал (%s) — переключаемся на Crawl4AI fallback",
            exc,
        )

    return await _parse_via_crawl4ai(days_ahead)


# ---------------------------------------------------------------------------
# Вспомогательные функции (используются нативным парсером)
# ---------------------------------------------------------------------------

_LEGAL_NOISE_RE = re.compile(
    r"(подлежат\s+обязательн|сертификац|лицензирован|"
    r"согласно\s+(законодательств|постановл)|налог(ов|ообложен))",
    re.IGNORECASE,
)


def _is_valid_event_title(title: str) -> bool:
    """Отсекает юридический мусор/длинные фразы, попавшие на irk.ru/afisha вне карточек.

    Карточка события на сайте — короткое название (до ~80 символов). Если HTML
    выдал текст длиннее 120 символов или содержит юридические триггеры
    («подлежат обязательной сертификации» и т. п.) — это попавший в общий поток
    блок текста о правилах сайта, не событие.
    """
    if not title or len(title) > 120:
        return False
    if _LEGAL_NOISE_RE.search(title):
        return False
    return True


def _parse_irk_html(html: str) -> list[dict[str, Any]]:
    """Парсинг HTML страницы irk.ru/afisha (обновлённая структура 2026)."""
    soup = BeautifulSoup(html, "html.parser")
    events = []

    date_pattern = re.compile(
        r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)"
        r"[,\s]+(?:пн|вт|ср|чт|пт|сб|вс)?\s*(\d{1,2}:\d{2})?",
        re.IGNORECASE
    )

    price_re = re.compile(
        r"(?:от\s+)?(\d{2,5})\s*(?:руб|₽|р\.?\b)",
        re.IGNORECASE,
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
    img_map = _build_image_url_map(soup)

    text_content = soup.get_text(separator="\n")
    lines = [line.strip() for line in text_content.split("\n") if line.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        date_match = date_pattern.search(line)
        if date_match:
            date_str = line
            time_raw = date_match.group(3)  # "HH:MM" или None
            title = ""
            genre = ""
            venue = ""
            age_restriction: str | None = None

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
                    if age_restriction is None:
                        age_restriction = candidate
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

            if (
                title
                and len(title) > 3
                and title.lower() not in skip_words
                and _is_valid_event_title(title)
            ):
                event_date = _parse_irk_date(date_str)
                event_id = generate_event_id(title, event_date, "irk")
                event_url = url_map.get(title.lower(), "https://irk.ru/afisha/")
                image_url = img_map.get(title.lower()[:60])
                location = venue if venue else "Иркутск"

                time_start: time | None = None
                if time_raw:
                    try:
                        hh, mm = time_raw.split(":")
                        time_start = time(int(hh), int(mm))
                    except (ValueError, TypeError):
                        time_start = None

                # Окно из ±5 строк вокруг даты для извлечения price/description
                window_start = max(0, i - 3)
                window_end = min(len(lines), i + 5)
                window_lines = lines[window_start:window_end]
                window_text = "\n".join(window_lines)

                # Цена
                price: str | None = None
                price_min: int | None = None
                pm = price_re.search(window_text)
                if pm:
                    try:
                        price_min = int(pm.group(1))
                        price = f"от {price_min} руб"
                    except (ValueError, TypeError):
                        pass

                # description не извлекаем: irk.ru/afisha не имеет описания на
                # главной странице, а соседние строки (lookahead) — это title
                # следующего события, что засоряет данные. Detail-страницы
                # отсутствуют. Оставляем None — direction-of-development.
                description: str | None = None

                events.append({
                    "id": event_id,
                    "title": title,
                    "description": description,
                    "date_start": event_date,
                    "event_type": detect_event_type(title, (genre or "") + " " + (description or "")),
                    "location": location,
                    "url": event_url,
                    "source": "irk",
                    "time_start": time_start,
                    "age_restriction": age_restriction,
                    "price": price,
                    "price_min": price_min,
                    "image_url": image_url,
                })

        i += 1

    seen_titles: set[str] = set()
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
        href_raw = a_tag.get("href")
        if not isinstance(href_raw, str) or not href_raw:
            continue
        href = href_raw
        text = a_tag.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if href.startswith("/"):
            href = f"https://irk.ru{href}"
        if "irk.ru" in href and "/afisha/" in href:
            url_map[text.lower()] = href
    return url_map


def _build_image_url_map(soup: BeautifulSoup) -> dict[str, str]:
    """Маппинг title (lowercase ключ, до 60 chars) → image_url из DOM.

    Стратегия: для каждого <img src> найти ближайший <a> или <h*>
    с текстом, использовать text как ключ. Lazy-loading через data-src fallback.
    Иконки/трекеры (по подстроке в URL) пропускаются.
    """
    img_map: dict[str, str] = {}
    for img in soup.find_all("img"):
        raw_src = img.get("src") or img.get("data-src")
        if not isinstance(raw_src, str) or not raw_src:
            continue
        src = raw_src.strip()
        if not src:
            continue
        # Skip иконок/трекеров
        lower_src = src.lower()
        if any(skip in lower_src for skip in ("icon", "logo", "pixel", "tracker", ".svg")):
            continue
        # Relative → absolute
        if src.startswith("//"):
            src = f"https:{src}"
        elif src.startswith("/"):
            src = f"https://irk.ru{src}"
        elif not src.startswith(("http://", "https://")):
            continue
        # Найти ближайший заголовок
        text = ""
        anchor = img.find_parent("a")
        if anchor:
            text = anchor.get_text(strip=True)
        if not text or len(text) < 5:
            h = img.find_next(["h2", "h3", "h4"])
            if h:
                text = h.get_text(strip=True)
        if text and len(text) >= 5:
            key = text.lower()[:60]
            img_map.setdefault(key, src)  # первое вхождение wins
    return img_map


def _parse_irk_date(date_str: str) -> str:
    """Парсинг даты в формате irk.ru.

    Примеры входных данных:
    - "3 февраля, вт 20:40"
    - "18 мая, вс 18:00"
    - "23 мая, пт 19:00"

    Returns:
        Дата в формате YYYY-MM-DD.
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
        logger.error("Ошибка парсинга даты '%s': %s", date_str, e)

    return str(date.today())


def generate_event_id(title: str, date_str: str, source: str = "irk") -> str:
    """Генерация уникального ID события."""
    content = f"{source}_{date_str}_{title}"
    return f"{source}_{hashlib.md5(content.encode()).hexdigest()[:12]}"
