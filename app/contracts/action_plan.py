from datetime import date as Date
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    model_validator,
)

from app.contracts.query_spec import (
    PeriodSpec,
    QuerySpec,
)
from app.core.enums import (
    FinancialNature,
    PlanStatus,
    TransactionDateType,
    TransactionDirection,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


# -----------------------------------------
# Shared semantic models
# -----------------------------------------

class SemanticTerms(StrictModel):
    financial_nature: FinancialNature | None = None

    concepts: list[str] = Field(
        default_factory=list
    )


class TransactionDateSpec(StrictModel):
    type: TransactionDateType

    # calendar_day:
    #
    # today     -> 0
    # yesterday -> -1
    offset: int = 0

    # exact_date only
    date: Date | None = None

    @model_validator(mode="after")
    def validate_date_spec(self):
        if (
            self.type
            == TransactionDateType.EXACT_DATE
            and self.date is None
        ):
            raise ValueError(
                "date is required when "
                "type='exact_date'."
            )

        return self


# -----------------------------------------
# CREATE TRANSACTION
# -----------------------------------------

class CreateTransactionParameters(StrictModel):
    amount_minor: PositiveInt

    currency: str = Field(
        default="SAR",
        min_length=3,
        max_length=3,
    )

    direction: TransactionDirection

    occurred_on: TransactionDateSpec = Field(
        default_factory=lambda: TransactionDateSpec(
            type=TransactionDateType.CALENDAR_DAY,
            offset=0,
        )
    )

    merchant_raw_name: str | None = None

    # Semantics inferred by the model.
    #
    # These are hints only.
    # Semantic Engine still validates them.
    semantic_hint: SemanticTerms | None = None

    # Semantics explicitly stated by the user.
    #
    # Example:
    # "كانت كتب"
    #
    # This has higher priority than semantic_hint.
    user_asserted_semantics: SemanticTerms | None = None


class CreateTransactionAction(StrictModel):
    action_id: str

    type: Literal[
        "create_transaction"
    ] = "create_transaction"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: CreateTransactionParameters


# -----------------------------------------
# UPDATE TRANSACTION
# -----------------------------------------

class TransactionTarget(StrictModel):
    transaction_id: str | None = None

    reference: Literal[
        "last_relevant_transaction"
    ] | None = None

    merchant: str | None = None

    amount_minor: PositiveInt | None = None

    period: PeriodSpec | None = None

    @model_validator(mode="after")
    def target_must_not_be_empty(self):
        if not any(
            [
                self.transaction_id,
                self.reference,
                self.merchant,
                self.amount_minor,
                self.period,
            ]
        ):
            raise ValueError(
                "Transaction target cannot be empty."
            )

        return self


class TransactionChanges(StrictModel):
    amount_minor: PositiveInt | None = None

    direction: TransactionDirection | None = None

    occurred_on: TransactionDateSpec | None = None

    merchant_raw_name: str | None = None

    semantic: SemanticTerms | None = None

    @model_validator(mode="after")
    def changes_must_not_be_empty(self):
        if not any(
            [
                self.amount_minor,
                self.direction,
                self.occurred_on,
                self.merchant_raw_name,
                self.semantic,
            ]
        ):
            raise ValueError(
                "Transaction changes cannot be empty."
            )

        return self


class UpdateTransactionParameters(StrictModel):
    target: TransactionTarget
    changes: TransactionChanges


class UpdateTransactionAction(StrictModel):
    action_id: str

    type: Literal[
        "update_transaction"
    ] = "update_transaction"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: UpdateTransactionParameters


# -----------------------------------------
# QUERY
# -----------------------------------------

class QueryFinancialDataAction(StrictModel):
    action_id: str

    type: Literal[
        "query_financial_data"
    ] = "query_financial_data"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: QuerySpec


# -----------------------------------------
# CONVERSATION
# -----------------------------------------

class ConversationResponseParameters(
    StrictModel
):
    mode: Literal[
        "acknowledgement",
        "general_response",
    ]

    topic: str | None = None


class ConversationResponseAction(StrictModel):
    action_id: str

    type: Literal[
        "conversation_response"
    ] = "conversation_response"

    depends_on: list[str] = Field(
        default_factory=list
    )

    parameters: ConversationResponseParameters


# -----------------------------------------
# ACTION UNION
# -----------------------------------------

Action = Annotated[
    Union[
        CreateTransactionAction,
        UpdateTransactionAction,
        QueryFinancialDataAction,
        ConversationResponseAction,
    ],
    Field(discriminator="type"),
]


# -----------------------------------------
# CLARIFICATION
# -----------------------------------------

class Clarification(StrictModel):
    reason: str

    missing_fields: list[str] = Field(
        default_factory=list
    )

    options: list[str] = Field(
        default_factory=list
    )


# -----------------------------------------
# RESPONSE CONTEXT PROPOSAL
# -----------------------------------------

class ResponseContext(StrictModel):
    topic: str | None = None

    metric: str | None = None

    concepts: list[str] = Field(
        default_factory=list
    )

    period: PeriodSpec | None = None


# -----------------------------------------
# ACTION PLAN
# -----------------------------------------

class ActionPlan(StrictModel):
    plan_version: Literal["1.0"] = "1.0"

    status: PlanStatus

    actions: list[Action] = Field(
        default_factory=list
    )

    clarification: Clarification | None = None

    unsupported_reason: str | None = None

    response_context: ResponseContext = Field(
        default_factory=ResponseContext
    )

    @model_validator(mode="after")
    def validate_plan_state(self):
        if self.status == PlanStatus.READY:
            if not self.actions:
                raise ValueError(
                    "A ready plan must contain "
                    "at least one action."
                )

            if self.clarification is not None:
                raise ValueError(
                    "A ready plan cannot contain "
                    "clarification."
                )

        elif (
            self.status
            == PlanStatus.NEEDS_CLARIFICATION
        ):
            if self.clarification is None:
                raise ValueError(
                    "needs_clarification requires "
                    "clarification details."
                )

        elif self.status == PlanStatus.UNSUPPORTED:
            if not self.unsupported_reason:
                raise ValueError(
                    "unsupported requires "
                    "unsupported_reason."
                )

        return self

    @model_validator(mode="after")
    def validate_dependencies(self):
        action_ids = [
            action.action_id
            for action in self.actions
        ]

        if len(action_ids) != len(set(action_ids)):
            raise ValueError(
                "action_id values must be unique."
            )

        valid_ids = set(action_ids)

        for action in self.actions:
            for dependency in action.depends_on:
                if dependency not in valid_ids:
                    raise ValueError(
                        f"Unknown dependency "
                        f"'{dependency}' "
                        f"in action '{action.action_id}'."
                    )

                if dependency == action.action_id:
                    raise ValueError(
                        "An action cannot depend on itself."
                    )

        return self