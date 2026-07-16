from pydantic import BaseModel, Field


class MetricsResponse(BaseModel):
    total_requests: int = 0
    successful: int = 0
    failed: int = 0
    by_category: dict[str, int] = Field(default_factory=dict)
    by_sentiment: dict[str, int] = Field(default_factory=dict)
    last_request_at: str | None = None
