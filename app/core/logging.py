import json
import logging
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.utils import client_ip, utcnow_iso


LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_REQUEST_ID_HEADER = "x-request-id"


def setup_logging() -> None:
    """Инициализация корневого логгера + ротация приложения. Идемпотентно."""
    logs_dir = Path(settings.storage_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FMT)

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    file_handler = RotatingFileHandler(
        logs_dir / "app.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Свой лог запросов пишется отдельным middleware — глушим стандартный uvicorn.access.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """
    Логирует каждый HTTP-запрос строкой JSONL в requests.log.
    Использует ротацию через отдельный логгер, чтобы файл не пух.
    Пробрасывает / принимает X-Request-Id для корреляции.
    """

    def __init__(self, app):
        super().__init__(app)
        self._logger = _build_requests_logger()

    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get(_REQUEST_ID_HEADER) or uuid.uuid4().hex[:12]
        request.state.request_id = req_id

        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers[_REQUEST_ID_HEADER] = req_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            entry = {
                "ts": utcnow_iso(),
                "id": req_id,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "ip": client_ip(request),
                "ua": request.headers.get("user-agent", ""),
                "ms": duration_ms,
            }
            self._logger.info(json.dumps(entry, ensure_ascii=False))


def _build_requests_logger() -> logging.Logger:
    logger = logging.getLogger("app.requests")
    if logger.handlers:
        return logger

    logs_dir = Path(settings.storage_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        logs_dir / "requests.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    # Пишем чистый JSONL — без префиксов вроде "INFO app.requests: ..."
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
