import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.enums import ContactCategory, InsightSource, Sentiment
from app.schemas.contact import ContactAiInsights, ContactRequest


log = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "Ты помогаешь разработчику разбирать входящие заявки с лендинга. "
    "Твоя задача — классифицировать обращение, определить тональность и составить "
    "короткий персонализированный ответ на русском языке от имени владельца сайта. "
    "Отвечай ТОЛЬКО валидным JSON, без комментариев и без markdown."
)


USER_PROMPT_TEMPLATE = """Заявка:
Имя: {name}
Email: {email}
Телефон: {phone}
Комментарий: {comment}

Верни JSON строго такой структуры:
{{
  "category": "job" | "project" | "collaboration" | "question" | "spam" | "other",
  "sentiment": "positive" | "neutral" | "negative",
  "reply_draft": "1-3 коротких абзаца ответа пользователю от первого лица, обращение на 'вы'"
}}

Правила:
- category: "job" — вакансия/оффер, "project" — заказ/разработка проекта, "collaboration" — коллаб/партнёрство, "question" — вопрос по опыту/технологиям, "spam" — реклама/спам, "other" — не подходит ни под одну.
- reply_draft: без воды, по делу, поблагодари, скажи что свяжешься, если это не спам.
- Только JSON, ничего больше."""


_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


async def analyze_contact(payload: ContactRequest) -> ContactAiInsights:
    """
    Классификация обращения + черновик ответа. При любой ошибке AI —
    graceful fallback на локальные эвристики, чтобы форма продолжала работать.
    """
    if not settings.openrouter_api_key:
        log.info("openrouter key missing, using fallback")
        return _fallback(payload)

    try:
        raw = await _call_openrouter(payload)
        parsed = _parse_json(raw)
        return ContactAiInsights(
            category=_safe_enum(ContactCategory, parsed.get("category"), ContactCategory.OTHER),
            sentiment=_safe_enum(Sentiment, parsed.get("sentiment"), Sentiment.NEUTRAL),
            reply_draft=str(parsed.get("reply_draft", "")).strip(),
            source=InsightSource.AI,
        )
    except Exception as e:
        log.warning("ai analysis failed, using fallback: %s", e)
        return _fallback(payload)


async def _call_openrouter(payload: ContactRequest) -> str:
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.openrouter_referer,
        "X-Title": settings.openrouter_app_title,
    }
    body = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_PROMPT_TEMPLATE.format(
                    name=payload.name,
                    email=payload.email,
                    phone=payload.phone,
                    comment=payload.comment,
                ),
            },
        ],
        "temperature": 0.4,
        "max_tokens": 500,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        raise ValueError("no choices in response")
    return choices[0].get("message", {}).get("content", "").strip()


def _parse_json(raw: str) -> dict[str, Any]:
    """Пытается разобрать чистый JSON, иначе — вытащить первый {...} из мусорного текста."""
    if not raw:
        raise ValueError("empty response")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = _JSON_OBJECT.search(raw)
        if not match:
            raise
        return json.loads(match.group(0))


def _safe_enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except (ValueError, TypeError):
        return default


_SPAM_MARKERS = ("http://", "https://", "казино", "seo продвижение", "1xbet", "промокод", "лотере")
_JOB_MARKERS = ("вакансия", "офер", "оффер", "предлагаю работ", "hh.ru", "нанять", "готовы предложить")
_PROJECT_MARKERS = ("разработ", "сайт", "лендинг", "проект", "бэкенд", "фронтенд", "приложение", "mvp", "бюджет")
_COLLAB_MARKERS = ("коллаб", "партнер", "партнёр", "совместн")
_QUESTION_MARKERS = ("вопрос", "как вы", "можете рассказать", "какой опыт", "почему", "интересно узнать")
_NEG_MARKERS = ("плохо", "ужасн", "разочарован", "не работает", "проблема", "недовол")
_POS_MARKERS = ("супер", "круто", "отличн", "нравится", "спасибо", "рад", "интересно")


def _match_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(m in text for m in markers)


def _fallback(payload: ContactRequest) -> ContactAiInsights:
    text = f"{payload.comment} {payload.name}".lower()

    if _match_any(text, _SPAM_MARKERS):
        category = ContactCategory.SPAM
    elif _match_any(text, _JOB_MARKERS):
        category = ContactCategory.JOB
    elif _match_any(text, _PROJECT_MARKERS):
        category = ContactCategory.PROJECT
    elif _match_any(text, _COLLAB_MARKERS):
        category = ContactCategory.COLLABORATION
    elif _match_any(text, _QUESTION_MARKERS):
        category = ContactCategory.QUESTION
    else:
        category = ContactCategory.OTHER

    if _match_any(text, _NEG_MARKERS):
        sentiment = Sentiment.NEGATIVE
    elif _match_any(text, _POS_MARKERS):
        sentiment = Sentiment.POSITIVE
    else:
        sentiment = Sentiment.NEUTRAL

    if category is ContactCategory.SPAM:
        reply = ""
    else:
        reply = (
            f"Здравствуйте, {payload.name}!\n\n"
            "Спасибо за ваше обращение — заявку получил. "
            "Свяжусь с вами в течение рабочего дня, чтобы обсудить детали.\n\n"
            "С уважением,\nКонстантин"
        )

    return ContactAiInsights(
        category=category,
        sentiment=sentiment,
        reply_draft=reply,
        source=InsightSource.FALLBACK,
    )
