from typing import Literal

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
# PARAMETERS
# =========================================================


class RecipeParameter(
    StrictModel
):

    name: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]*$",
    )

    kind: Literal[
        "period",
        "merchant",
        "concept",
        "number",
        "text",
    ]

    source: Literal[
        "user",
        "derived",
        "runtime",
    ]

    required: bool = True

    derivation: Literal[
        "previous_period",
        "same_elapsed_previous_period",
    ] | None = None

    description: str = Field(
        min_length=1,
        max_length=300,
    )

    @model_validator(
        mode="after"
    )
    def validate_parameter(
        self,
    ):

        if (
            self.source == "derived"
            and self.derivation is None
        ):

            raise ValueError(
                "Derived parameters require "
                "a derivation strategy."
            )

        if (
            self.source != "derived"
            and self.derivation is not None
        ):

            raise ValueError(
                "Only derived parameters may "
                "define derivation."
            )

        return self


# =========================================================
# STEPS
# =========================================================


class RecipeStep(
    StrictModel
):

    step_id: str = Field(
        min_length=1,
        max_length=40,
        pattern=r"^[a-z][a-z0-9_]*$",
    )

    operation: Literal[
        "verify_data_coverage",
        "snapshot",
        "aggregate_spending",
        "compare_spending_periods",
        "rank_dimension",
        "rank_dimension_delta",
        "reconcile_dimension_delta",
        "list_transactions",
    ]

    purpose: str = Field(
        min_length=1,
        max_length=300,
    )

    target_period_param: str | None = (
        None
    )

    comparison_period_param: str | None = (
        None
    )

    dimension: Literal[
        "merchant",
        "concept",
        "day",
        "weekday",
        "financial_nature",
        "source",
    ] | None = None

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )

    order: Literal[
        "amount_desc",
        "amount_asc",
        "count_desc",
        "count_asc",
        "delta_desc",
        "delta_asc",
    ] | None = None

    spending_only: bool = True

    @model_validator(
        mode="after"
    )
    def validate_step(
        self,
    ):

        if (
            self.operation
            == "verify_data_coverage"
        ):

            if (
                self.target_period_param
                is None
            ):

                raise ValueError(
                    "verify_data_coverage "
                    "requires target_period_param."
                )

        if (
            self.operation
            == "aggregate_spending"
        ):

            if (
                self.target_period_param
                is None
            ):

                raise ValueError(
                    "aggregate_spending "
                    "requires target_period_param."
                )

        if (
            self.operation
            == "compare_spending_periods"
        ):

            if (
                self.target_period_param
                is None
                or self.comparison_period_param
                is None
            ):

                raise ValueError(
                    "compare_spending_periods "
                    "requires target and "
                    "comparison periods."
                )

        if self.operation in {
            "rank_dimension_delta",
            "reconcile_dimension_delta",
        }:

            if (
                self.target_period_param
                is None
                or self.comparison_period_param
                is None
            ):

                raise ValueError(
                    f"{self.operation} requires "
                    "target and comparison periods."
                )

            if self.dimension is None:

                raise ValueError(
                    f"{self.operation} requires "
                    "a dimension."
                )

        if (
            self.operation
            == "rank_dimension"
        ):

            if (
                self.target_period_param
                is None
            ):

                raise ValueError(
                    "rank_dimension requires "
                    "target_period_param."
                )

            if self.dimension is None:

                raise ValueError(
                    "rank_dimension requires "
                    "a dimension."
                )

        if (
            self.operation
            == "list_transactions"
            and self.target_period_param
            is None
        ):

            raise ValueError(
                "list_transactions requires "
                "target_period_param."
            )

        return self


# =========================================================
# COMPILED RECIPE
# =========================================================


class CompiledRecipe(
    StrictModel
):

    version: Literal[1] = 1

    name: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
    )

    objective: str = Field(
        min_length=10,
        max_length=500,
    )

    parameters: list[
        RecipeParameter
    ] = Field(
        min_length=1,
        max_length=10,
    )

    steps: list[
        RecipeStep
    ] = Field(
        min_length=1,
        max_length=10,
    )

    trigger_examples: list[
        str
    ] = Field(
        min_length=3,
        max_length=8,
    )

    @model_validator(
        mode="after"
    )
    def validate_recipe(
        self,
    ):

        parameter_names = {
            parameter.name
            for parameter
            in self.parameters
        }

        step_ids = [
            step.step_id
            for step
            in self.steps
        ]

        if (
            len(step_ids)
            != len(set(step_ids))
        ):

            raise ValueError(
                "Recipe step IDs "
                "must be unique."
            )

        for step in self.steps:

            references = [
                step.target_period_param,
                step.comparison_period_param,
            ]

            for reference in references:

                if (
                    reference is not None
                    and reference
                    not in parameter_names
                ):

                    raise ValueError(
                        "Recipe step references "
                        "an undefined parameter: "
                        f"{reference}"
                    )

        return self


# =========================================================
# COMPILATION DECISION
# =========================================================


class RecipeCompilationDecision(
    StrictModel
):

    reusable: bool

    reason: str = Field(
        min_length=1,
        max_length=500,
    )

    recipe: (
        CompiledRecipe
        | None
    ) = None

    @model_validator(
        mode="after"
    )
    def validate_decision(
        self,
    ):

        if (
            self.reusable
            and self.recipe is None
        ):

            raise ValueError(
                "Reusable compilation "
                "requires recipe."
            )

        if (
            not self.reusable
            and self.recipe is not None
        ):

            raise ValueError(
                "Non-reusable compilation "
                "must not contain recipe."
            )

        return self