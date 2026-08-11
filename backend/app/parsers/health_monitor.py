"""Мониторинг здоровья парсеров.

Отслеживает:
- Количество событий от каждого парсера
- Ошибки и их частоту
- Алерты при аномалиях

Если парсер возвращает 0 событий - это сигнал что что-то сломалось.
"""

import logging
from datetime import datetime, timedelta
from collections.abc import Callable
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class ParserHealth:
    """Состояние здоровья парсера."""
    name: str
    last_run: datetime | None = None
    last_success: datetime | None = None
    last_count: int = 0
    avg_count: float = 0.0
    total_runs: int = 0
    total_errors: int = 0
    consecutive_failures: int = 0
    history: list[dict] = field(default_factory=list)
    
    def record_run(self, count: int, success: bool, error: str | None = None):
        """Записать результат запуска."""
        now = datetime.now()
        self.last_run = now
        self.total_runs += 1
        
        if success and count > 0:
            self.last_success = now
            self.last_count = count
            self.consecutive_failures = 0
            # Обновляем среднее
            self.avg_count = (self.avg_count * (self.total_runs - 1) + count) / self.total_runs
        else:
            self.total_errors += 1
            self.consecutive_failures += 1
        
        # Сохраняем в историю (последние 100 запусков)
        self.history.append({
            "time": now.isoformat(),
            "count": count,
            "success": success,
            "error": error,
        })
        if len(self.history) > 100:
            self.history = self.history[-100:]
    
    def is_healthy(self) -> bool:
        """Проверить здоровье парсера."""
        # Нездоров если:
        # 1. Больше 3 последовательных ошибок
        # 2. Последний успешный запуск > 24 часов назад
        # 3. Возвращает намного меньше чем обычно
        
        if self.consecutive_failures >= 3:
            return False
        
        if self.last_success:
            if datetime.now() - self.last_success > timedelta(hours=24):
                return False
        
        if self.avg_count > 0 and self.last_count < self.avg_count * 0.3:
            return False  # Меньше 30% от обычного
        
        return True
    
    def get_status(self) -> str:
        """Получить статус."""
        if self.consecutive_failures >= 3:
            return "CRITICAL"
        elif self.consecutive_failures >= 1:
            return "WARNING"
        elif self.last_count == 0 and self.total_runs > 0:
            return "EMPTY"
        else:
            return "OK"
    
    def to_dict(self) -> dict:
        """Конвертировать в словарь."""
        return {
            "name": self.name,
            "status": self.get_status(),
            "healthy": self.is_healthy(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "last_count": self.last_count,
            "avg_count": round(self.avg_count, 1),
            "total_runs": self.total_runs,
            "total_errors": self.total_errors,
            "consecutive_failures": self.consecutive_failures,
            "error_rate": round(self.total_errors / max(1, self.total_runs) * 100, 1),
        }


class HealthMonitor:
    """Монитор здоровья всех парсеров."""
    
    def __init__(self, state_file: str = ".cache/parser_health.json"):
        self.parsers: dict[str, ParserHealth] = {}
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.alert_callbacks: list[Callable] = []
        self._load_state()
    
    def _load_state(self):
        """Загрузить сохранённое состояние."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                for name, state in data.items():
                    self.parsers[name] = ParserHealth(
                        name=name,
                        last_count=state.get("last_count", 0),
                        avg_count=state.get("avg_count", 0.0),
                        total_runs=state.get("total_runs", 0),
                        total_errors=state.get("total_errors", 0),
                    )
            except Exception as e:
                logger.warning(f"Не удалось загрузить состояние: {e}")
    
    def _save_state(self):
        """Сохранить состояние."""
        try:
            data = {name: p.to_dict() for name, p in self.parsers.items()}
            with open(self.state_file, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Не удалось сохранить состояние: {e}")
    
    def register_alert_callback(self, callback: Callable[[str, str, dict], None]):
        """Зарегистрировать callback для алертов."""
        self.alert_callbacks.append(callback)
    
    def _send_alert(self, parser_name: str, alert_type: str, details: dict):
        """Отправить алерт."""
        logger.warning(f"ALERT [{alert_type}] {parser_name}: {details}")
        for callback in self.alert_callbacks:
            try:
                callback(parser_name, alert_type, details)
            except Exception as e:
                logger.error(f"Ошибка callback алерта: {e}")
    
    def record(self, parser_name: str, count: int, success: bool = True, error: str | None = None):
        """Записать результат парсера."""
        if parser_name not in self.parsers:
            self.parsers[parser_name] = ParserHealth(name=parser_name)
        
        parser = self.parsers[parser_name]
        old_status = parser.get_status()
        
        parser.record_run(count, success, error)
        
        new_status = parser.get_status()
        
        # Проверяем нужен ли алерт
        if new_status != old_status:
            if new_status == "CRITICAL":
                self._send_alert(parser_name, "CRITICAL", {
                    "message": f"Парсер {parser_name} критически сломан",
                    "consecutive_failures": parser.consecutive_failures,
                    "last_error": error,
                })
            elif new_status == "WARNING":
                self._send_alert(parser_name, "WARNING", {
                    "message": f"Парсер {parser_name} показывает ошибки",
                    "count": count,
                    "error": error,
                })
            elif new_status == "OK" and old_status in ["CRITICAL", "WARNING"]:
                self._send_alert(parser_name, "RECOVERED", {
                    "message": f"Парсер {parser_name} восстановился",
                    "count": count,
                })
        
        # Алерт если мало данных
        if success and count > 0 and parser.avg_count > 5:
            if count < parser.avg_count * 0.3:
                self._send_alert(parser_name, "LOW_DATA", {
                    "message": f"Парсер {parser_name} вернул мало данных",
                    "count": count,
                    "avg_count": parser.avg_count,
                })
        
        self._save_state()
    
    def get_status(self) -> dict[str, Any]:
        """Получить общий статус."""
        healthy = sum(1 for p in self.parsers.values() if p.is_healthy())
        total = len(self.parsers)
        
        return {
            "overall": "OK" if healthy == total else ("WARNING" if healthy > 0 else "CRITICAL"),
            "healthy_count": healthy,
            "total_count": total,
            "parsers": {name: p.to_dict() for name, p in self.parsers.items()},
        }
    
    def get_summary(self) -> str:
        """Получить краткую сводку."""
        lines = ["=== Статус парсеров ==="]
        for name, parser in self.parsers.items():
            status = parser.get_status()
            icon = {"OK": "✅", "WARNING": "⚠️", "CRITICAL": "❌", "EMPTY": "📭"}.get(status, "❓")
            lines.append(f"{icon} {name}: {parser.last_count} событий (avg: {parser.avg_count:.0f})")
        return "\n".join(lines)


# Глобальный экземпляр
health_monitor = HealthMonitor()


# Декоратор для автоматического мониторинга
def monitored(parser_name: str):
    """Декоратор для автоматического мониторинга парсера."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                count = len(result) if result else 0
                health_monitor.record(parser_name, count, success=True)
                return result
            except Exception as e:
                health_monitor.record(parser_name, 0, success=False, error=str(e))
                raise
        return wrapper
    return decorator


# === Тест ===

if __name__ == "__main__":
    print("=== Тест Health Monitor ===\n")
    
    monitor = HealthMonitor(state_file=".cache/test_health.json")
    
    # Симулируем работу парсеров
    monitor.record("kassir", 17)
    monitor.record("yandex", 19)
    monitor.record("telegram", 29)
    monitor.record("zeroevent", 55)
    
    print(monitor.get_summary())
    print()
    
    # Симулируем ошибку
    monitor.record("kassir", 0, success=False, error="Timeout")
    monitor.record("kassir", 0, success=False, error="Timeout")
    monitor.record("kassir", 0, success=False, error="Timeout")
    
    print("\nПосле ошибок:")
    print(monitor.get_summary())
    
    # Восстановление
    monitor.record("kassir", 15)
    
    print("\nПосле восстановления:")
    print(monitor.get_summary())
    
    print("\n" + "=" * 40)
    print("Детальный статус:")
    import json
    print(json.dumps(monitor.get_status(), indent=2, ensure_ascii=False, default=str))
