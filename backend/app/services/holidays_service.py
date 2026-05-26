"""Сервис для работы с праздниками России."""
import holidays
from datetime import date, timedelta


class HolidaysService:
    """Сервис для получения информации о праздниках и школьных каникул."""

    def __init__(self):
        # Праздники России на несколько лет вперёд
        self._holidays: dict[int, holidays.Russia] = {}

        # Школьные каникулы (семейный туризм)
        # Источник: Минпросвещения России
        self._school_holidays: list[tuple] = [
            # 2025-2026 учебный год
            (date(2025, 10, 25), date(2025, 11, 4), "Осенние каникулы"),
            (date(2025, 12, 31), date(2026, 1, 11), "Зимние каникулы"),
            (date(2026, 2, 21), date(2026, 3, 1), "Дополнительные каникулы (1 класс)"),
            (date(2026, 3, 28), date(2026, 4, 5), "Весенние каникулы"),
            (date(2026, 5, 27), date(2026, 8, 31), "Летние каникулы"),
            # 2024-2025 учебный год (для истории)
            (date(2024, 10, 26), date(2024, 11, 3), "Осенние каникулы"),
            (date(2024, 12, 28), date(2025, 1, 8), "Зимние каникулы"),
            (date(2025, 3, 22), date(2025, 3, 30), "Весенние каникулы"),
            (date(2025, 5, 26), date(2025, 8, 31), "Летние каникулы"),
        ]

    def _get_holidays_for_year(self, year: int) -> holidays.Russia:
        """Получить праздники для года (с кэшированием)."""
        if year not in self._holidays:
            self._holidays[year] = holidays.Russia(years=year)
        return self._holidays[year]
    
    def is_holiday(self, d: date) -> bool:
        """Проверить, является ли дата праздником."""
        ru_holidays = self._get_holidays_for_year(d.year)
        return d in ru_holidays
    
    def get_holiday_name(self, d: date) -> str | None:
        """Получить название праздника или None."""
        ru_holidays = self._get_holidays_for_year(d.year)
        return ru_holidays.get(d)
    
    def days_to_nearest_holiday(self, d: date, max_days: int = 30) -> int:
        """
        Количество дней до ближайшего праздника.
        
        Returns:
            0 если сегодня праздник, иначе количество дней (макс max_days)
        """
        if self.is_holiday(d):
            return 0
        
        ru_holidays = self._get_holidays_for_year(d.year)
        # Также проверяем следующий год если близко к концу года
        if d.month >= 11:
            next_year = self._get_holidays_for_year(d.year + 1)
            all_dates = set(ru_holidays.keys()) | set(next_year.keys())
        else:
            all_dates = set(ru_holidays.keys())
        
        future_holidays = [h for h in all_dates if h > d]
        if not future_holidays:
            return max_days
        
        nearest = min(future_holidays)
        days = (nearest - d).days
        return min(days, max_days)
    
    def is_long_weekend(self, d: date) -> bool:
        """
        Проверить, является ли дата частью длинных выходных.
        
        Длинные выходные = праздник + примыкающие выходные дни.
        """
        # Проверяем текущий день и соседние
        for offset in range(-3, 4):
            check_date = d + timedelta(days=offset)
            if self.is_holiday(check_date):
                # Если праздник близко к выходным
                if check_date.weekday() in [0, 4]:  # Пн или Пт
                    return True
        return False
    
    def get_holidays_in_range(
        self, 
        date_from: date, 
        date_to: date
    ) -> list[dict]:
        """
        Получить список праздников в диапазоне дат.
        
        Returns:
            [{"date": date, "name": str}, ...]
        """
        result = []
        
        # Собираем праздники за все годы в диапазоне
        years = set(range(date_from.year, date_to.year + 1))
        for year in years:
            ru_holidays = self._get_holidays_for_year(year)
            for d, name in ru_holidays.items():
                if date_from <= d <= date_to:
                    result.append({"date": d, "name": name})
        
        return sorted(result, key=lambda x: x["date"])
    
    def is_school_holiday(self, d: date) -> bool:
        """Проверить, является ли дата школьными каникулами."""
        for start, end, _ in self._school_holidays:
            if start <= d <= end:
                return True
        return False
    
    def get_school_holiday_name(self, d: date) -> str | None:
        """Получить название школьных каникул или None."""
        for start, end, name in self._school_holidays:
            if start <= d <= end:
                return name
        return None
    
    def days_to_school_holiday(self, d: date, max_days: int = 30) -> int:
        """Количество дней до ближайших школьных каникул."""
        if self.is_school_holiday(d):
            return 0
        
        future_starts = [start for start, _, _ in self._school_holidays if start > d]
        if not future_starts:
            return max_days
        
        nearest = min(future_starts)
        days = (nearest - d).days
        return min(days, max_days)
    
    def get_holiday_features(self, d: date) -> dict:
        """
        Получить все фичи праздников для даты.
        
        Returns:
            {
                "is_holiday": bool,
                "holiday_name": str | None,
                "days_to_holiday": int,
                "is_long_weekend": bool,
                "is_pre_holiday": bool,  # День перед праздником
                "is_post_holiday": bool, # День после праздника
                "is_school_holiday": bool,  # Школьные каникулы
                "days_to_school_holiday": int,
            }
        """
        return {
            "is_holiday": self.is_holiday(d),
            "holiday_name": self.get_holiday_name(d),
            "days_to_holiday": self.days_to_nearest_holiday(d),
            "is_long_weekend": self.is_long_weekend(d),
            "is_pre_holiday": self.is_holiday(d + timedelta(days=1)),
            "is_post_holiday": self.is_holiday(d - timedelta(days=1)),
            "is_school_holiday": self.is_school_holiday(d),
            "days_to_school_holiday": self.days_to_school_holiday(d),
        }


# Глобальный экземпляр
holidays_service = HolidaysService()
