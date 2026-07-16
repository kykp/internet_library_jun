import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.errors import EmailSendError
from app.schemas.contact import ContactAiInsights, ContactRequest
from app.services import email_templates as tpl


log = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15


async def send_owner_notification(
    payload: ContactRequest,
    insights: ContactAiInsights,
    request_id: str,
) -> None:
    await _send(
        to=[settings.owner_email],
        subject=tpl.owner_subject(payload),
        text=tpl.owner_text(payload, insights, request_id),
        html_body=tpl.owner_html(payload, insights, request_id),
        reply_to=payload.email,
    )


async def send_user_confirmation(payload: ContactRequest, insights: ContactAiInsights) -> None:
    await _send(
        to=[payload.email],
        subject=tpl.user_subject(),
        text=tpl.user_text(payload, insights),
        html_body=tpl.user_html(payload, insights),
    )


async def _send(
    *,
    to: list[str],
    subject: str,
    text: str,
    html_body: str,
    reply_to: str | None = None,
) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise EmailSendError("SMTP не сконфигурирован")

    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")

    # 465 → implicit SSL; 587 → STARTTLS.
    use_ssl = settings.smtp_port == 465
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=use_ssl,
            start_tls=not use_ssl and settings.smtp_use_tls,
            timeout=SMTP_TIMEOUT_SECONDS,
        )
        log.info("email sent to %s: %s", to, subject)
    except (aiosmtplib.SMTPException, OSError, TimeoutError) as e:
        # Не отдаём деталь SMTP наружу — только в лог. Клиенту — общий текст.
        log.error("smtp send failed to %s: %s", to, e)
        raise EmailSendError("Не удалось отправить письмо") from e
