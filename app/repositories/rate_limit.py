import asyncio
import json
import time
from pathlib import Path

from app.core.config import settings


class RateLimitStore:
    """
    Файловое хранилище IP → [timestamps] (sliding window).
    Устаревшие записи чистятся лениво: только для затрагиваемого ключа при каждом запросе,
    и полный prune раз в PRUNE_EVERY_N_HITS попаданий.
    """

    PRUNE_EVERY_N_HITS = 50

    def __init__(self, path: Path | None = None):
        self.path = path or Path(settings.storage_dir) / "rate_limit.json"
        self._lock = asyncio.Lock()
        self._writes_since_prune = 0

    def _load_sync(self) -> dict[str, list[float]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_sync(self, data: dict[str, list[float]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f)
        tmp.replace(self.path)

    async def check_and_hit(self, key: str, *, max_hits: int, window: int) -> tuple[bool, int, int]:
        """Возвращает (allowed, remaining, retry_after_seconds)."""
        async with self._lock:
            data = await asyncio.to_thread(self._load_sync)
            now = time.time()
            hits = [t for t in data.get(key, []) if now - t < window]

            if len(hits) >= max_hits:
                oldest = min(hits)
                retry_after = max(int(window - (now - oldest)) + 1, 1)
                data[key] = hits
                await self._persist(data, now, window)
                return False, 0, retry_after

            hits.append(now)
            data[key] = hits
            await self._persist(data, now, window)
            return True, max_hits - len(hits), 0

    async def _persist(self, data: dict[str, list[float]], now: float, window: int) -> None:
        self._writes_since_prune += 1
        if self._writes_since_prune >= self.PRUNE_EVERY_N_HITS:
            self._prune(data, now, window)
            self._writes_since_prune = 0
        await asyncio.to_thread(self._save_sync, data)

    @staticmethod
    def _prune(data: dict[str, list[float]], now: float, window: int) -> None:
        stale = []
        for k, ts_list in data.items():
            fresh = [t for t in ts_list if now - t < window]
            if fresh:
                data[k] = fresh
            else:
                stale.append(k)
        for k in stale:
            data.pop(k, None)


_store: RateLimitStore | None = None


def get_rate_limit_store() -> RateLimitStore:
    global _store
    if _store is None:
        _store = RateLimitStore()
    return _store
