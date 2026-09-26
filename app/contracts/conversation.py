from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class ConversationResolution(
    StrictModel
):
    """
    Semantic resolution of the user's current message
    against recent conversation context.

    This model does NOT answer the user and does NOT
    contain financial results.
    """

    relation: Literal[
        "standalone",
        "follow_up",
    ]

    used_context: bool

    resolved_message: str = Field(
        min_length=1,
        max_length=4000,
    )

    reference_summary: str | None = Field(
        default=None,
        max_length=600,
    )
