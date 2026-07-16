from fastapi import APIRouter

from app.repositories.metrics import get_metrics_store
from app.schemas.metrics import MetricsResponse


router = APIRouter()


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Агрегированная статистика обращений",
    description="Счётчики: всего, успешных/провальных, разбивка по категории/тональности.",
)
async def metrics() -> MetricsResponse:
    data = await get_metrics_store().snapshot()
    return MetricsResponse(**data)
