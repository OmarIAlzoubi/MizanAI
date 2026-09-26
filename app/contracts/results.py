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


class ActionExecutionResult(StrictModel):
    action_id: str
    action_type: str

    status: Literal[
        "success"
    ] = "success"

    data: dict[str, Any] = Field(
        default_factory=dict
    )


class PlanExecutionResult(StrictModel):
    status: Literal[
        "success"
    ] = "success"

    actions: list[
        ActionExecutionResult
    ] = Field(
        default_factory=list
    )