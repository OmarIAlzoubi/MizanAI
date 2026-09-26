from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
)

from app.core.enums import (
    FinancialNature,
    TransactionDirection,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class TransactionRecord(StrictModel):
    id: str

    account_id: str = "primary"

    amount_minor: PositiveInt
    currency: str = Field(
        min_length=3,
        max_length=3,
    )

    direction: TransactionDirection

    occurred_at_utc: datetime

    status: Literal[
        "posted",
        "pending",
    ] = "posted"

    merchant_raw_name: str | None = None
    raw_description: str | None = None

    source: Literal[
        "chat",
        "manual",
        "import",
    ] = "chat"

    created_at_utc: datetime


class SemanticAnnotationRecord(StrictModel):
    id: str
    transaction_id: str

    financial_nature: FinancialNature

    concepts: list[str] = Field(
        default_factory=list
    )

    source: Literal[
        "llm_inference",
        "user_asserted",
        "mixed",
        "system",
    ]

    version: PositiveInt = 1

    is_active: bool = True

    created_at_utc: datetime

class ActivityTransactionRecord(StrictModel):
    id: str

    amount_minor: int
    currency: str

    direction: TransactionDirection

    occurred_at_utc: datetime

    merchant_raw_name: str | None = None
    raw_description: str | None = None

    financial_nature: FinancialNature | None = None

    concepts: list[str] = Field(
        default_factory=list
    )