from typing import (
    Any,
    Literal,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class StrictModel(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )


# =========================================================
# RESOLVED PERIOD
# =========================================================


class ResolvedRecipePeriod(
    StrictModel
):

    name: str

    requested_start: str

    requested_end: str

    start: str

    end: str

    clipped_by_coverage: bool = False


# =========================================================
# EXECUTION STEP
# =========================================================


class RecipeExecutionStep(
    StrictModel
):

    step_id: str

    operation: str

    purpose: str

    status: Literal[
        "ok",
        "error",
    ]

    sql: str | None = None

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


# =========================================================
# EXECUTION RESULT
# =========================================================


class RecipeExecutionResult(
    StrictModel
):

    type: Literal[
        "recipe_execution"
    ] = "recipe_execution"

    status: Literal[
        "completed",
        "needs_fallback",
        "failed",
    ]

    recipe_id: str

    recipe_name: str

    user_message: str

    parameters: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    coverage_end_local_date: (
        str | None
    ) = None

    steps: list[
        RecipeExecutionStep
    ] = Field(
        default_factory=list
    )

    fallback_reason: (
        str | None
    ) = None