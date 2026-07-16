from fastapi import APIRouter, Depends, Request, status

from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact import process_contact
from app.services.rate_limit import enforce_contact_rate_limit


router = APIRouter()


@router.post(
    "/contact",
    response_model=ContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Приём заявки с лендинга",
    description=(
        "Принимает данные контактной формы, валидирует их, применяет rate limit, "
        "прогоняет через AI-анализ (категория / тональность / черновик ответа) "
        "и отправляет два письма: владельцу сайта и пользователю."
    ),
    responses={
        200: {"description": "Заявка принята"},
        422: {"description": "Ошибка валидации"},
        429: {"description": "Превышен лимит запросов"},
        502: {"description": "Не удалось отправить письмо владельцу"},
    },
)
async def create_contact(
    payload: ContactRequest,
    request: Request,
    _: None = Depends(enforce_contact_rate_limit),
) -> ContactResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    return await process_contact(payload, request_id)
