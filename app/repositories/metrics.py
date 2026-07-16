import asyncio
import copy
import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.utils import utcnow_iso


_DEFAULT: dict[str, Any] = {
    "total_requests": 0,
    "successful": 0,
    "failed": 0,
    "by_category": {},
    "by_sentiment": {},
    "last_request_at": None,
}


class MetricsStore:
    """Файловое хранилище агрегированных метрик обращений."""

    def __init__(self, path: Path | None = None):
        self.path = path or Path(settings.storage_dir) / "metrics.json"
        self._lock = asyncio.Lock()

    def _load_sync(self) -> dict[str, Any]:
        if not self.path.exists():
            return copy.deepcopy(_DEFAULT)
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return copy.deepcopy(_DEFAULT)
            for k, default_value in _DEFAULT.items():
                data.setdefault(k, copy.deepcopy(default_value))
            return data
        except (json.JSONDecodeError, OSError):
            return copy.deepcopy(_DEFAULT)

    def _save_sync(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    async def record(
        self,
        *,
        success: bool,
        category: str | None = None,
        sentiment: str | None = None,
    ) -> None:
        async with self._lock:
            data = await asyncio.to_thread(self._load_sync)
            data["total_requests"] += 1
            data["successful" if success else "failed"] += 1
            if category:
                data["by_category"][category] = data["by_category"].get(category, 0) + 1
            if sentiment:
                data["by_sentiment"][sentiment] = data["by_sentiment"].get(sentiment, 0) + 1
            data["last_request_at"] = utcnow_iso()
            await asyncio.to_thread(self._save_sync, data)

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            return await asyncio.to_thread(self._load_sync)


_store: MetricsStore | None = None


def get_metrics_store() -> MetricsStore:
    global _store
    if _store is None:
        _store = MetricsStore()
    return _store
