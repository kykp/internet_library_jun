import pytest

from app.core.enums import ContactCategory, InsightSource, Sentiment
from app.schemas.contact import ContactRequest
from app.services.ai import analyze_contact


def _payload(comment: str) -> ContactRequest:
    return ContactRequest(
        name="Иван",
        email="ivan@example.com",
        phone="+7 999 123-45-67",
        comment=comment,
    )


@pytest.mark.asyncio
async def test_fallback_detects_job():
    insights = await analyze_contact(_payload(
        "У нас открыта вакансия на backend-разработчика, готовы предложить оффер."
    ))
    assert insights.source is InsightSource.FALLBACK
    assert insights.category is ContactCategory.JOB


@pytest.mark.asyncio
async def test_fallback_detects_spam():
    insights = await analyze_contact(_payload(
        "Купите SEO продвижение недорого — акция http://spam.example"
    ))
    assert insights.category is ContactCategory.SPAM
    assert insights.reply_draft == ""  # спамерам не отвечаем


@pytest.mark.asyncio
async def test_fallback_neutral_default():
    insights = await analyze_contact(_payload("Здравствуйте, интересно ваше мнение."))
    assert insights.sentiment in (Sentiment.NEUTRAL, Sentiment.POSITIVE)
    assert insights.reply_draft  # должен быть шаблон


@pytest.mark.asyncio
async def test_fallback_when_api_returns_error(monkeypatch):
    from app.core import config
    monkeypatch.setattr(config.settings, "openrouter_api_key", "sk-test")

    async def _boom(_):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.services.ai._call_openrouter", _boom)
    insights = await analyze_contact(_payload("Нужна разработка сайта."))
    assert insights.source is InsightSource.FALLBACK
