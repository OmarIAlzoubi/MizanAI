from datetime import date as Date
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    model_validator,
)

from app.core.enums import (
    FinancialNature,
    GroupBy,
    Metric,
    PeriodType,
    PlanStatus,
    SortDirection,
    TransactionDirection,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


# =========================================================
# CREATE TRANSACTION
# =========================================================

class LLMCreateTransactionParameters(StrictModel):
    amount_minor: PositiveInt

    currency: str = Field(
        default="SAR",
        min_length=3,
        max_length=3,
    )

    direction: TransactionDirection

    # Keep date representation compact for the LLM.
    date_type: Literal[
        "calendar_day",
        "exact_date",
    ] = "calendar_day"

    # today = 0
    # yesterday = -1
    day_offset: int = 0

    exact_date: Date | None = None

    merchant: str | None = None

    # AI inference
    inferred_financial_nature: (
        FinancialNature | None
    ) = None

    inferred_concepts: list[str] = Field(
        default_factory=list
    )

    # Only when explicitly stated/corrected
    # by the user.
    asserted_financial_nature: (
        FinancialNature | None
    ) = None

    asserted_concepts: list[str] = Field(
        default_factory=list
    )


class LLMCreateTransactionAction(StrictModel):
    action_id: str

    type: Literal[
        "create_transaction"
    ] = "create_transaction"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: LLMCreateTransactionParameters


# =========================================================
# UPDATE TRANSACTION
# =========================================================

class LLMUpdateTransactionParameters(StrictModel):
    # Target
    transaction_id: str | None = None

    reference: Literal[
        "last_relevant_transaction"
    ] | None = None

    target_merchant: str | None = None
    target_amount_minor: PositiveInt | None = None

    target_period_type: PeriodType | None = None
    target_period_offset: int = 0

    # Changes
    new_amount_minor: PositiveInt | None = None

    new_merchant: str | None = None

    inferred_financial_nature: (
        FinancialNature | None
    ) = None

    inferred_concepts: list[str] = Field(
        default_factory=list
    )

    asserted_financial_nature: (
        FinancialNature | None
    ) = None

    asserted_concepts: list[str] = Field(
        default_factory=list
    )


class LLMUpdateTransactionAction(StrictModel):
    action_id: str

    type: Literal[
        "update_transaction"
    ] = "update_transaction"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: LLMUpdateTransactionParameters


# =========================================================
# QUERY FINANCIAL DATA
# =========================================================

class LLMQueryParameters(StrictModel):
    metric: Metric

    period_type: PeriodType

    period_offset: int = 0

    days: int | None = Field(
        default=None,
        ge=1,
        le=3650,
    )

    months: int | None = Field(
        default=None,
        ge=1,
        le=120,
    )

    start_date: Date | None = None
    end_date: Date | None = None

    concepts: list[str] = Field(
        default_factory=list
    )

    merchants: list[str] = Field(
        default_factory=list
    )

    financial_natures: list[
        FinancialNature
    ] = Field(
        default_factory=list
    )

    group_by: GroupBy | None = None

    # For V1 we expose only the two useful
    # comparison modes to Grok.
    comparison: Literal[
        "previous_period",
        "user_baseline",
    ] | None = None

    sort: SortDirection | None = None

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    @model_validator(
        mode="after"
    )
    def validate_period_shape(
        self
    ):

        has_start = (
            self.start_date
            is not None
        )

        has_end = (
            self.end_date
            is not None
        )

        # An explicit range must have
        # both boundaries.
        if has_start != has_end:

            raise ValueError(
                "Explicit query periods require "
                "both start_date and end_date."
            )

        if has_start and has_end:

            if (
                self.start_date
                > self.end_date
            ):

                raise ValueError(
                    "start_date cannot be "
                    "after end_date."
                )

            if (
                self.days is not None
                or self.months is not None
            ):

                raise ValueError(
                    "Explicit dates cannot be "
                    "combined with days/months."
                )

            if self.period_offset != 0:

                raise ValueError(
                    "Explicit dates cannot be "
                    "combined with a non-zero "
                    "period_offset."
                )

        return self


class LLMQueryFinancialDataAction(StrictModel):
    action_id: str

    type: Literal[
        "query_financial_data"
    ] = "query_financial_data"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: LLMQueryParameters


# =========================================================
# CONVERSATION
# =========================================================

class LLMConversationParameters(StrictModel):
    mode: Literal[
        "acknowledgement",
        "general_response",
    ]

    topic: str | None = None


class LLMConversationResponseAction(StrictModel):
    action_id: str

    type: Literal[
        "conversation_response"
    ] = "conversation_response"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: LLMConversationParameters


# =========================================================
# ACTION UNION
# =========================================================

LLMAction = Annotated[
    Union[
        LLMCreateTransactionAction,
        LLMUpdateTransactionAction,
        LLMQueryFinancialDataAction,
        LLMConversationResponseAction,
    ],
    Field(discriminator="type"),
]


# =========================================================
# PLAN
# =========================================================

# =========================================================
# PLAN
# =========================================================


class LLMClarification(StrictModel):

    reason: str

    missing_fields: list[str] = Field(
        default_factory=list
    )

    options: list[str] = Field(
        default_factory=list
    )


class LLMActionPlan(StrictModel):

    # =====================================================
    # CAPABILITY ROUTING
    # =====================================================

    route: Literal[
        "legacy",
        "agent",
    ]

    route_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    route_reason: str = Field(
        min_length=1,
        max_length=300,
    )

    agent_task: str | None = Field(
        default=None,
        max_length=600,
    )

    # =====================================================
    # ACTION PLAN
    # =====================================================

    plan_version: Literal[
        "1.0"
    ] = "1.0"

    status: PlanStatus | None = None

    actions: list[LLMAction] = Field(
        default_factory=list
    )

    clarification: (
        LLMClarification | None
    ) = None

    unsupported_reason: (
        str | None
    ) = None