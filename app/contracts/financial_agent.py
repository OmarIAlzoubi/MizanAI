from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


# =========================================================
# AGENT DECISION
# =========================================================


class FinancialAgentDecision(StrictModel):

    action: Literal[
        "query",
        "final",
    ]

    # Why the agent wants this query.
    purpose: str | None = Field(
        default=None,
        max_length=500,
    )

    # Populated only for action=query.
    sql: str | None = None

    # Populated only for action=final.
    answer: str | None = None

    @model_validator(
        mode="after"
    )
    def validate_decision(self):

        if self.action == "query":

            if not self.sql:
                raise ValueError(
                    "sql is required when "
                    "action=query."
                )

            if not self.purpose:
                raise ValueError(
                    "purpose is required when "
                    "action=query."
                )

            self.answer = None

        elif self.action == "final":

            if not self.answer:
                raise ValueError(
                    "answer is required when "
                    "action=final."
                )

            self.sql = None
            self.purpose = None

        return self


# =========================================================
# EXECUTION TRACE
# =========================================================


class FinancialAgentStep(StrictModel):

    step: int

    purpose: str

    sql: str

    status: Literal[
        "ok",
        "error",
    ]

    columns: list[str] = Field(
        default_factory=list
    )

    rows: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    row_count: int = 0

    truncated: bool = False

    error: str | None = None


class FinancialAgentExecutionResult(
    StrictModel
):

    type: Literal[
        "financial_agent"
    ] = "financial_agent"

    status: Literal[
        "completed",
        "failed",
    ]

    task: str

    answer: str

    steps: list[
        FinancialAgentStep
    ] = Field(
        default_factory=list
    )