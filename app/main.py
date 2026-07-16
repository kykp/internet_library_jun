from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import contact, health, metrics
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestLogMiddleware, setup_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    storage = Path(settings.storage_dir)
    (storage / "logs").mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Developer Landing API",
        description=(
            "Backend для лендинга-презентации: контактная форма с AI-обработкой "
            "и email-уведомлениями."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Middleware выполняются в обратном порядке регистрации. Хотим, чтобы request-id
    # был выставлен до gzip/cors — регистрируем request-log первым.
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-Id"],
        expose_headers=["X-Request-Id"],
    )

    register_exception_handlers(app)

    app.include_router(contact.router, prefix="/api", tags=["contact"])
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(metrics.router, prefix="/api", tags=["metrics"])

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
