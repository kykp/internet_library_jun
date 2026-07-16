from fastapi import APIRouter

from app.core.config import settings
from app.schemas.health import HealthResponse


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка статуса сервиса",
    description="Возвращает `ok`, если SMTP и AI сконфигурированы; иначе `degraded`.",
)
async def health() -> HealthResponse:
    checks = {
        "smtp": "ok" if settings.smtp_user and settings.smtp_password else "missing",
        "ai": "ok" if settings.openrouter_api_key else "fallback_only",
    }
    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return HealthResponse(status=overall, checks=checks)
