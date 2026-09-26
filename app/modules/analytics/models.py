from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.core.enums import Metric


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class FinancialQueryResult(StrictModel):
    metric: Metric

    amount_minor: int = 0
    currency: str

    transaction_count: int = 0

    period_start_utc: datetime | None = None
    period_end_utc: datetime | None = None

    concepts: list[str] = Field(
        default_factory=list
    )