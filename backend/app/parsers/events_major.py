"""Крупные события Прибайкалья — вручную собранные данные.

Эти события имеют высокий impact на загрузку отелей и подтверждены
из официальных источников.

ВАЖНО: Данные по загрузке отелей НЕ собирались июнь-сентябрь 2025.
Поэтому события летнего сезона не влияют на обучение моделей.
"""
from datetime import date
from typing import Any
import hashlib


def get_major_events_2025_2026() -> list[dict[str, Any]]:
    """
    Крупные события Иркутской области за март 2025 — февраль 2026.
    
    Период совпадает с данными загрузки отелей.
    Источники: официальные сайты, СМИ, подтверждённые анонсы.
    """
    events = [
        # ============ ФЕВРАЛЬ-МАРТ 2025 (ЗИМНИЙ СЕЗОН) ============
        {
            "title": "Olkhon Ice Fest 2025",
            "description": "VI Международный фестиваль ледовых скульптур на острове Ольхон. "
                          "Более 37000 посетителей. Парк ледовых скульптур, мастер-классы, фотозоны.",
            "date_start": "2025-02-15",
            "date_end": "2025-03-15",
            "event_type": "festival",
            "location": "о. Ольхон, Хужир",
            "visitors": 37000,
            "impact": "very_high",
            "source_url": "https://olkhonicefest.ru/",
        },
        {
            "title": "Baikal Race 2025 — гонка на собачьих упряжках",
            "description": "Международная гонка на собачьих упряжках по льду Байкала. "
                          "Дистанция 200+ км.",
            "date_start": "2025-02-20",
            "date_end": "2025-02-26",
            "event_type": "sport",
            "location": "оз. Байкал",
            "visitors": 500,
            "impact": "medium",
        },
        {
            "title": "Байкальская Миля 2025",
            "description": "Фестиваль скорости на льду Байкала. Гонки на автомобилях, "
                          "мотоциклах и другой технике. 90 пилотов, 41 команда.",
            "date_start": "2025-03-07",
            "date_end": "2025-03-11",
            "event_type": "sport",
            "location": "оз. Байкал",
            "visitors": 3000,
            "impact": "high",
            "source_url": "https://baikalskayamilya.ru/",
        },
        
        # ============ МАЙ 2025 (МАЙСКИЕ ПРАЗДНИКИ) ============
        {
            "title": "Майские праздники 2025",
            "description": "Праздник Весны и Труда, День Победы. Массовые мероприятия, "
                          "парад Победы, концерты.",
            "date_start": "2025-05-01",
            "date_end": "2025-05-10",
            "event_type": "holiday",
            "location": "Иркутск, область",
            "visitors": 100000,
            "impact": "very_high",
        },
        {
            "title": "Парад Победы в Иркутске",
            "description": "Военный парад в честь 80-летия Победы в Великой Отечественной войне.",
            "date_start": "2025-05-09",
            "date_end": None,
            "event_type": "holiday",
            "location": "Иркутск, центр",
            "visitors": 50000,
            "impact": "very_high",
        },
        
        # ============ ДЕКАБРЬ 2025 ============
        {
            "title": "Новогодние праздники 2025-2026",
            "description": "Новогодние и рождественские каникулы. Ёлки, ярмарки, концерты. "
                          "Пик зимнего туризма.",
            "date_start": "2025-12-31",
            "date_end": "2026-01-08",
            "event_type": "holiday",
            "location": "Иркутская область",
            "visitors": 200000,
            "impact": "very_high",
        },
        
        # ============ ЯНВАРЬ 2026 ============
        {
            "title": "Цирк на льду «По щучьему велению»",
            "description": "Новогоднее шоу в Ледовом дворце «Айсберг».",
            "date_start": "2026-01-02",
            "date_end": "2026-01-10",
            "event_type": "theater",
            "location": "ЛД «Айсберг», Иркутск",
            "visitors": 10000,
            "impact": "high",
        },
        
        # ============ ФЕВРАЛЬ 2026 ============
        {
            "title": "Olkhon Ice Fest 2026",
            "description": "VII Международный фестиваль ледовых скульптур на острове Ольхон.",
            "date_start": "2026-02-15",
            "date_end": "2026-03-15",
            "event_type": "festival",
            "location": "о. Ольхон, Хужир",
            "visitors": 40000,
            "impact": "very_high",
            "source_url": "https://olkhonicefest.ru/",
        },
        {
            "title": "Концерт группы «Ленинград»",
            "description": "Два концерта Сергея Шнурова в Ледовом дворце «Айсберг». "
                          "Билеты 4500-16000 руб.",
            "date_start": "2026-02-27",
            "date_end": "2026-02-28",
            "event_type": "concert",
            "location": "ЛД «Айсберг», ул. Лермонтова 255/1, Иркутск",
            "visitors": 15000,
            "impact": "very_high",
            "source_url": "https://iceberg-irk.ru/",
        },
    ]
    
    # Добавляем ID и source к каждому событию
    result = []
    for event in events:
        content = f"major_{event['date_start']}_{event['title']}"
        event_id = f"major_{hashlib.md5(content.encode()).hexdigest()[:12]}"
        
        result.append({
            "id": event_id,
            "title": event["title"],
            "description": event["description"],
            "date_start": event["date_start"],
            "date_end": event.get("date_end"),
            "event_type": event.get("event_type", "event"),
            "location": event.get("location", "Иркутск"),
            "source": "manual",
            "url": event.get("source_url"),
            "image_url": None,
            "visitors": event.get("visitors"),
            "impact": event.get("impact", "medium"),
        })
    
    return result


def get_school_holidays_2025_2026() -> list[dict[str, Any]]:
    """
    Школьные каникулы 2025-2026 — влияют на семейный туризм.
    
    Источник: Минпросвещения России.
    """
    holidays = [
        {
            "title": "Осенние школьные каникулы",
            "date_start": "2025-10-25",
            "date_end": "2025-11-04",
            "event_type": "school_holiday",
            "impact": "high",
        },
        {
            "title": "Зимние школьные каникулы",
            "date_start": "2025-12-31",
            "date_end": "2026-01-11",
            "event_type": "school_holiday",
            "impact": "very_high",
        },
        {
            "title": "Дополнительные каникулы (1 класс)",
            "date_start": "2026-02-21",
            "date_end": "2026-03-01",
            "event_type": "school_holiday",
            "impact": "medium",
        },
    ]
    
    result = []
    for h in holidays:
        content = f"school_{h['date_start']}_{h['title']}"
        event_id = f"school_{hashlib.md5(content.encode()).hexdigest()[:12]}"
        
        result.append({
            "id": event_id,
            "title": h["title"],
            "description": f"Школьные каникулы — пик семейного туризма",
            "date_start": h["date_start"],
            "date_end": h["date_end"],
            "event_type": h["event_type"],
            "location": "Россия",
            "source": "manual",
            "url": None,
            "impact": h["impact"],
        })
    
    return result
