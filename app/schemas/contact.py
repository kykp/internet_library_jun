import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.enums import ContactCategory, InsightSource, Sentiment


PHONE_ALLOWED = re.compile(r"^[\d+\-\s()]+$")
PHONE_DIGITS = re.compile(r"\D")


class ContactRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="Имя отправителя")
    email: EmailStr = Field(description="Email отправителя")
    phone: str = Field(min_length=6, max_length=32, description="Телефон в свободном формате")
    comment: str = Field(min_length=5, max_length=2000, description="Текст обращения")

    @field_validator("name", "comment")
    @classmethod
    def _strip_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("поле не может быть пустым")
        return v

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, v: str) -> str:
        v = v.strip()
        if not PHONE_ALLOWED.match(v):
            raise ValueError("телефон содержит недопустимые символы")
        digits = PHONE_DIGITS.sub("", v)
        if not 6 <= len(digits) <= 15:
            raise ValueError("некорректная длина номера телефона")
        return v


class ContactAiInsights(BaseModel):
    category: ContactCategory = ContactCategory.OTHER
    sentiment: Sentiment = Sentiment.NEUTRAL
    reply_draft: str = ""
    source: InsightSource = InsightSource.FALLBACK


class ContactResponse(BaseModel):
    ok: bool = True
    request_id: str
    insights: ContactAiInsights
    message: str = "Спасибо, ваша заявка принята. Мы свяжемся с вами в ближайшее время."
