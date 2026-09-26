from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.contracts.action_plan import (
    ActionPlan,
)


class StrictModel(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )


class UnderstandingDecision(
    StrictModel
):

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

    # Only legacy requests have
    # a deterministic ActionPlan.
    plan: ActionPlan | None = None

    @model_validator(
        mode="after"
    )
    def validate_route(self):

        if self.route == "legacy":

            if self.plan is None:

                raise ValueError(
                    "Legacy route requires "
                    "an ActionPlan."
                )

            if self.agent_task is not None:

                raise ValueError(
                    "Legacy route must not "
                    "contain agent_task."
                )

        if self.route == "agent":

            if not self.agent_task:

                raise ValueError(
                    "Agent route requires "
                    "agent_task."
                )

            if self.plan is not None:

                raise ValueError(
                    "Agent route must not "
                    "contain a legacy ActionPlan."
                )

        return self