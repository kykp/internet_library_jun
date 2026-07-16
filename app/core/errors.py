import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


log = logging.getLogger(__name__)


class AppError(Exception):
    """Базовое доменное исключение — маппится глобальным handler'ом в JSON-ответ."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class RateLimitError(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    code = "rate_limited"


class EmailSendError(AppError):
    status_code = HTTPStatus.BAD_GATEWAY
    code = "email_failed"


def _error_body(
    code: str,
    message: str,
    request_id: str | None = None,
    details: Any = None,
) -> dict:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if request_id:
        body["request_id"] = request_id
    if details is not None:
        body["error"]["details"] = details
    return body


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        log.warning("app error [%s]: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, _request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(x) for x in e.get("loc", [])[1:]) or "body",
                "message": e.get("msg", "invalid"),
            }
            for e in exc.errors()
        ]
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=_error_body(
                "validation_error",
                "Проверьте корректность введённых данных",
                _request_id(request),
                details,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            HTTPStatus.NOT_FOUND: "not_found",
            HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
        }.get(HTTPStatus(exc.status_code), "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail), _request_id(request)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=_error_body(
                "internal_error",
                "Внутренняя ошибка сервера",
                _request_id(request),
            ),
        )
