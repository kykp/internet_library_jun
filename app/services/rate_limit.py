from fastapi import Request

from app.core.config import settings
from app.core.errors import RateLimitError
from app.core.utils import client_ip
from app.repositories.rate_limit import get_rate_limit_store


async def enforce_contact_rate_limit(request: Request) -> None:
    """FastAPI-dependency: ограничивает частоту заявок с одного IP."""
    ip = client_ip(request)
    allowed, _remaining, retry_after = await get_rate_limit_store().check_and_hit(
        key=f"contact:{ip}",
        max_hits=settings.rate_limit_max,
        window=settings.rate_limit_window_seconds,
    )
    if not allowed:
        raise RateLimitError(
            f"Слишком много запросов. Повторите через {retry_after} сек.",
        )
