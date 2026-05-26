"""Health-tracking парсеров через Redis hash."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal

from app.constants import SCHEDULER_JOB_INTERVALS_HOURS
from app.services.cache_service import cache_service

HEALTH_KEY = "parser_health"  # Redis hash, ключи — parser_id, value — JSON
_HEALTH_TTL = 7 * 24 * 3600  # 7 дней
_STALE_MULTIPLIER = 2.0  # is_stale если last_run был >2x ожидаемого интервала назад

_CREDENTIAL_PATTERNS = [
    re.compile(r"://[^:]+:[^@]+@", re.IGNORECASE),
    re.compile(r"password\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*=\s*\S+", re.IGNORECASE),
    re.compile(r"token\s*=\s*\S+", re.IGNORECASE),
]


def sanitize_error(msg: str) -> str:
    """Удалить credentials из сообщения об ошибке перед записью в Redis."""
    for pat in _CREDENTIAL_PATTERNS:
        msg = pat.sub("[REDACTED]", msg)
    return msg


class ParserHealthService:
    async def report(
        self,
        *,
        parser_id: str,
        status: Literal["ok", "warn", "fail"],
        items_collected: int = 0,
        error: str | None = None,
    ) -> None:
        if cache_service.client is None or not cache_service.is_connected:
            return
        try:
            safe_error = sanitize_error(error)[:500] if error else None
            payload = {
                "parser_id": parser_id,
                "status": status,
                "items_collected": items_collected,
                "error": safe_error,
                "last_run": datetime.now(timezone.utc).isoformat(),
            }
            await cache_service.client.hset(HEALTH_KEY, parser_id, json.dumps(payload))
            await cache_service.client.expire(HEALTH_KEY, _HEALTH_TTL)
        except Exception:
            return

    async def list_all(self) -> list[dict]:
        if cache_service.client is None or not cache_service.is_connected:
            return []
        try:
            raw = await cache_service.client.hgetall(HEALTH_KEY)
        except Exception:
            return []
        out: list[dict] = []
        now = datetime.now(timezone.utc)
        for _parser_id, payload in raw.items():
            try:
                entry = json.loads(payload)
            except Exception:
                continue
            enriched = self._enrich_freshness(entry, now)
            out.append(enriched)
        out.sort(key=lambda x: x.get("last_run") or "", reverse=True)
        return out

    @staticmethod
    def _enrich_freshness(entry: dict, now: datetime) -> dict:
        """Дополняет entry полями is_stale, last_run_age_minutes, expected_interval_minutes."""
        parser_id = entry.get("parser_id") or ""
        last_run_iso = entry.get("last_run")
        interval_hours = _resolve_interval_hours(parser_id)

        age_minutes: float | None = None
        is_stale = False
        next_expected_iso: str | None = None
        if last_run_iso:
            try:
                last_run = datetime.fromisoformat(last_run_iso)
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                age_minutes = (now - last_run).total_seconds() / 60.0
                if interval_hours:
                    threshold_minutes = interval_hours * 60.0 * _STALE_MULTIPLIER
                    is_stale = age_minutes > threshold_minutes
                    next_expected = last_run.timestamp() + interval_hours * 3600.0
                    next_expected_iso = datetime.fromtimestamp(
                        next_expected, tz=timezone.utc
                    ).isoformat()
            except Exception:
                pass

        entry["last_run_age_minutes"] = round(age_minutes, 1) if age_minutes is not None else None
        entry["expected_interval_minutes"] = (
            round(interval_hours * 60.0, 1) if interval_hours else None
        )
        entry["next_expected_run"] = next_expected_iso
        entry["is_stale"] = is_stale
        return entry

    async def is_stale(self, parser_id: str) -> bool:
        """True если последний успешный запуск parser_id был >2x ожидаемого интервала назад."""
        if cache_service.client is None or not cache_service.is_connected:
            return False
        try:
            raw = await cache_service.client.hget(HEALTH_KEY, parser_id)
        except Exception:
            return False
        if not raw:
            return False
        try:
            entry = json.loads(raw)
        except Exception:
            return False
        enriched = self._enrich_freshness(entry, datetime.now(timezone.utc))
        return bool(enriched.get("is_stale"))


def _resolve_interval_hours(parser_id: str) -> float | None:
    """Маппинг parser_id → ожидаемый интервал в часах из SCHEDULER_JOB_INTERVALS_HOURS.

    parser_id из BaseParser обычно совпадает с источником (irk, kassir, telegram, ...).
    Аггрегируем event-источники в один "events" интервал.
    """
    pid = parser_id.lower()
    if pid in SCHEDULER_JOB_INTERVALS_HOURS:
        return SCHEDULER_JOB_INTERVALS_HOURS[pid]
    if pid.startswith("hotels") or pid == "101hotels":
        return SCHEDULER_JOB_INTERVALS_HOURS.get("hotels")
    if pid.startswith("weather") or pid == "openmeteo":
        return SCHEDULER_JOB_INTERVALS_HOURS.get("weather")
    if pid.startswith("telegram"):
        return SCHEDULER_JOB_INTERVALS_HOURS.get("telegram")
    # все остальные event-парсеры (irk, kassir, yandex, zeroevent, culture38, culture_rf)
    return SCHEDULER_JOB_INTERVALS_HOURS.get("events")


parser_health_service = ParserHealthService()
