from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class MonthlySpendingPoint(StrictModel):
    month: str
    amount_minor: int


class CategorySpendingPoint(StrictModel):
    concept: str
    amount_minor: int


class DashboardSummary(StrictModel):

    current_balance_minor: int

    current_month_spending_minor: int

    previous_month_spending_minor: int

    change_percent: float | None = None

    monthly_spending: list[
        MonthlySpendingPoint
    ] = Field(
        default_factory=list
    )

    top_categories: list[
        CategorySpendingPoint
    ] = Field(
        default_factory=list
    )

    insight: str