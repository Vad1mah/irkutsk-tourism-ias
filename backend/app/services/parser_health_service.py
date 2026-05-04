"""Health-tracking парсеров через Redis hash."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Literal

from app.services.cache_service import cache_service

HEALTH_KEY = "parser_health"  # Redis hash, ключи — parser_id, value — JSON


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
            payload = {
                "parser_id": parser_id,
                "status": status,
                "items_collected": items_collected,
                "error": error,
                "last_run": datetime.utcnow().isoformat(),
            }
            await cache_service.client.hset(HEALTH_KEY, parser_id, json.dumps(payload))
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
        for parser_id_bytes, payload_bytes in raw.items():
            try:
                pid = parser_id_bytes.decode() if isinstance(parser_id_bytes, bytes) else parser_id_bytes
                p = payload_bytes.decode() if isinstance(payload_bytes, bytes) else payload_bytes
                out.append(json.loads(p))
            except Exception:
                continue
        out.sort(key=lambda x: x.get("last_run") or "", reverse=True)
        return out


parser_health_service = ParserHealthService()
