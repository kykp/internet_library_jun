from enum import StrEnum


class ContactCategory(StrEnum):
    JOB = "job"
    PROJECT = "project"
    COLLABORATION = "collaboration"
    QUESTION = "question"
    SPAM = "spam"
    OTHER = "other"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class InsightSource(StrEnum):
    AI = "ai"
    FALLBACK = "fallback"
