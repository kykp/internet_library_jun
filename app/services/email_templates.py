import html

from app.schemas.contact import ContactAiInsights, ContactRequest


_USER_FALLBACK_TEXT = (
    "Спасибо за ваше обращение. Я получил вашу заявку и отвечу в ближайшее время.\n\n"
    "С уважением,\nКонстантин"
)


def owner_subject(payload: ContactRequest) -> str:
    return f"Новая заявка с лендинга — {payload.name}"


def owner_text(payload: ContactRequest, insights: ContactAiInsights, request_id: str) -> str:
    return (
        f"Новая заявка с лендинга (id: {request_id})\n\n"
        f"Имя: {payload.name}\n"
        f"Email: {payload.email}\n"
        f"Телефон: {payload.phone}\n\n"
        f"Комментарий:\n{payload.comment}\n\n"
        f"--- Автоматический анализ ---\n"
        f"Категория: {insights.category.value}\n"
        f"Тональность: {insights.sentiment.value}\n"
        f"Источник: {insights.source.value}\n"
        f"Черновик ответа:\n{insights.reply_draft or '—'}\n"
    )


def owner_html(payload: ContactRequest, insights: ContactAiInsights, request_id: str) -> str:
    return f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:600px;color:#222;">
      <h2 style="margin:0 0 12px 0;">Новая заявка</h2>
      <p style="color:#888;font-size:12px;margin:0 0 16px 0;">id: {html.escape(request_id)}</p>
      <table style="border-collapse:collapse;width:100%;">
        <tr><td style="padding:6px 0;color:#888;width:120px;">Имя</td><td>{html.escape(payload.name)}</td></tr>
        <tr><td style="padding:6px 0;color:#888;">Email</td><td>{html.escape(payload.email)}</td></tr>
        <tr><td style="padding:6px 0;color:#888;">Телефон</td><td>{html.escape(payload.phone)}</td></tr>
      </table>
      <h3 style="margin:20px 0 6px 0;">Комментарий</h3>
      <div style="background:#f6f6f6;padding:12px;border-radius:6px;white-space:pre-wrap;">{html.escape(payload.comment)}</div>
      <h3 style="margin:20px 0 6px 0;">Автоматический анализ</h3>
      <ul style="margin:0;padding-left:18px;">
        <li>Категория: <b>{html.escape(insights.category.value)}</b></li>
        <li>Тональность: <b>{html.escape(insights.sentiment.value)}</b></li>
        <li>Источник: {html.escape(insights.source.value)}</li>
      </ul>
      <h3 style="margin:20px 0 6px 0;">Черновик ответа</h3>
      <div style="background:#eef6ff;padding:12px;border-radius:6px;white-space:pre-wrap;">{html.escape(insights.reply_draft or '—')}</div>
    </div>
    """


def user_subject() -> str:
    return "Заявка получена, спасибо за обращение"


def _user_body(payload: ContactRequest, insights: ContactAiInsights) -> str:
    reply = insights.reply_draft.strip()
    if reply:
        return reply
    return f"Здравствуйте, {payload.name}!\n\n{_USER_FALLBACK_TEXT}"


def user_text(payload: ContactRequest, insights: ContactAiInsights) -> str:
    body = _user_body(payload, insights)
    return f"{body}\n\n---\nЭто автоматическое подтверждение получения вашей заявки."


def user_html(payload: ContactRequest, insights: ContactAiInsights) -> str:
    body_html = html.escape(_user_body(payload, insights)).replace("\n", "<br>")
    return f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:560px;color:#222;">
      <div style="line-height:1.5;">{body_html}</div>
      <hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
      <p style="color:#999;font-size:12px;">Это автоматическое подтверждение получения вашей заявки.</p>
    </div>
    """
