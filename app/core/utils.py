from datetime import datetime, timezone

from starlette.requests import Request


def client_ip(request: Request) -> str:
    """Реальный IP клиента с учётом X-Forwarded-For (за прокси/Render/nginx)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def utcnow_iso() -> str:
    """UTC-время в ISO 8601, без завязки на локальную зону сервера."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
