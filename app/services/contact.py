import asyncio
import logging

from app.core.enums import ContactCategory
from app.core.errors import EmailSendError
from app.repositories.metrics import get_metrics_store
from app.schemas.contact import ContactAiInsights, ContactRequest, ContactResponse
from app.services.ai import analyze_contact
from app.services.email import send_owner_notification, send_user_confirmation


log = logging.getLogger(__name__)


async def process_contact(payload: ContactRequest, request_id: str) -> ContactResponse:
    """
    Оркестрация обработки заявки:
      1) AI-анализ (с graceful fallback);
      2) отправка писем — владельцу (обязательно) и пользователю (best effort, кроме спама);
      3) запись метрик, ответ клиенту.
    """
    insights = await analyze_contact(payload)

    owner_ok, user_ok = await _dispatch_emails(payload, insights, request_id)

    await get_metrics_store().record(
        success=owner_ok,
        category=insights.category.value,
        sentiment=insights.sentiment.value,
    )

    if not owner_ok:
        raise EmailSendError("Заявку не удалось передать владельцу. Попробуйте позже.")

    message = _build_user_message(user_ok, insights.category)
    return ContactResponse(
        ok=True,
        request_id=request_id,
        insights=insights,
        message=message,
    )


async def _dispatch_emails(
    payload: ContactRequest,
    insights: ContactAiInsights,
    request_id: str,
) -> tuple[bool, bool]:
    """
    Параллельная отправка писем. Владельцу — критично, пользователю — best effort
    (и вообще не шлём, если это спам).
    """
    send_user = insights.category is not ContactCategory.SPAM

    coros = [send_owner_notification(payload, insights, request_id)]
    if send_user:
        coros.append(send_user_confirmation(payload, insights))

    results = await asyncio.gather(*coros, return_exceptions=True)
    owner_result = results[0]
    user_result = results[1] if send_user else None

    owner_ok = _log_email_result("owner", owner_result, request_id, level=logging.ERROR)
    if send_user:
        user_ok = _log_email_result("user", user_result, request_id, level=logging.WARNING)
    else:
        user_ok = True  # намеренно не отправляли — считаем «ок» для сообщения пользователю
    return owner_ok, user_ok


def _log_email_result(kind: str, result, request_id: str, *, level: int) -> bool:
    if result is None or not isinstance(result, BaseException):
        return True
    if isinstance(result, EmailSendError):
        log.log(level, "%s email failed [%s]: %s", kind, request_id, result.message)
    else:
        log.log(level, "%s email crashed [%s]: %r", kind, request_id, result)
    return False


def _build_user_message(user_ok: bool, category: ContactCategory) -> str:
    if category is ContactCategory.SPAM:
        return "Спасибо, ваша заявка принята."
    if user_ok:
        return "Спасибо, ваша заявка принята. Копия ответа отправлена вам на email."
    return "Спасибо, ваша заявка принята. Копию письма отправить не удалось — проверьте email."
