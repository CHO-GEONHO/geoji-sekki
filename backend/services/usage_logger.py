"""API 사용량 로거 — ~/Library/Python/dashboard-data/monitoring/usage-geoji-sekki.json"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("geojisekki.usage")

APP_ID = "geoji-sekki"
USAGE_FILE = (
    Path.home() / "Library/Python/dashboard-data/monitoring/usage-geoji-sekki.json"
)

_lock = asyncio.Lock()


async def record(
    provider: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: float = 0.0,
    error: bool = False,
) -> None:
    today = datetime.now().strftime("%Y-%m-%d")

    async with _lock:
        try:
            data = json.loads(USAGE_FILE.read_text()) if USAGE_FILE.exists() else {"app_id": APP_ID, "daily": {}}
        except Exception:
            data = {"app_id": APP_ID, "daily": {}}

        entry = (
            data["daily"]
            .setdefault(today, {})
            .setdefault(provider, {"input_tokens": 0, "output_tokens": 0, "calls": 0, "errors": 0, "latency_avg_ms": 0})
        )

        if error:
            entry["errors"] += 1
        else:
            prev_calls = entry["calls"]
            prev_avg = entry["latency_avg_ms"]
            entry["calls"] += 1
            entry["input_tokens"] += input_tokens
            entry["output_tokens"] += output_tokens
            entry["latency_avg_ms"] = round(
                (prev_avg * prev_calls + latency_ms) / entry["calls"], 1
            )

        try:
            USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.warning("usage 로그 쓰기 실패: %s", e)
