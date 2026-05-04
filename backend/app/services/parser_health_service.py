"""Health-tracking парсеров через Redis hash."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal

from app.services.cache_service import cache_service

HEALTH_KEY = "parser_health"  # Redis hash, ключи — parser_id, value — JSON
_HEALTH_TTL = 7 * 24 * 3600  # 7 дней

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
        for _parser_id, payload in raw.items():
            try:
                out.append(json.loads(payload))
            except Exception:
                continue
        out.sort(key=lambda x: x.get("last_run") or "", reverse=True)
        return out


parser_health_service = ParserHealthService()
