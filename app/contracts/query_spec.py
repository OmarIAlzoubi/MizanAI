from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.core.enums import (
    ComparisonType,
    FinancialNature,
    GroupBy,
    Metric,
    PeriodType,
    SortDirection,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid"
    )


class PeriodSpec(StrictModel):
    type: PeriodType

    # Used by calendar periods.
    #
    # current month:
    # offset = 0
    #
    # previous month:
    # offset = -1
    offset: int = 0

    # Used only by rolling periods.
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

    # Explicit calendar dates.
    # When present, the validator normalizes
    # the period to absolute_range.
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_period(self):

        has_start = (
            self.start_date
            is not None
        )

        has_end = (
            self.end_date
            is not None
        )

        # =================================================
        # EXPLICIT DATES
        #
        # If explicit dates are present, they are the
        # authoritative representation of the requested
        # period. Normalize the period to ABSOLUTE_RANGE so
        # downstream code cannot accidentally interpret it
        # as "today", "last week", etc.
        # =================================================

        if has_start or has_end:

            if not (
                has_start
                and has_end
            ):
                raise ValueError(
                    "Explicit periods require both "
                    "start_date and end_date."
                )

            if (
                self.start_date
                > self.end_date
            ):
                raise ValueError(
                    "start_date cannot be after end_date."
                )

            # Canonicalize contradictory LLM output.
            #
            # Example:
            # calendar_day + offset=0
            # + start_date=2026-09-10
            #
            # becomes:
            # absolute_range + 2026-09-10..2026-09-10
            self.type = (
                PeriodType.ABSOLUTE_RANGE
            )

            self.offset = 0
            self.days = None
            self.months = None

            return self

        # =================================================
        # ABSOLUTE RANGE
        # =================================================

        if (
            self.type
            == PeriodType.ABSOLUTE_RANGE
        ):
            raise ValueError(
                "absolute_range requires "
                "start_date and end_date."
            )

        # =================================================
        # ROLLING DAYS
        # =================================================

        if (
            self.type
            == PeriodType.ROLLING_DAYS
        ):

            if self.days is None:
                raise ValueError(
                    "days is required for "
                    "rolling_days."
                )

            if self.months is not None:
                raise ValueError(
                    "rolling_days cannot use months."
                )

            if self.offset != 0:
                raise ValueError(
                    "rolling_days cannot use offset."
                )

            return self

        # =================================================
        # ROLLING MONTHS
        # =================================================

        if (
            self.type
            == PeriodType.ROLLING_MONTHS
        ):

            if self.months is None:
                raise ValueError(
                    "months is required for "
                    "rolling_months."
                )

            if self.days is not None:
                raise ValueError(
                    "rolling_months cannot use days."
                )

            if self.offset != 0:
                raise ValueError(
                    "rolling_months cannot use offset."
                )

            return self

        # =================================================
        # CALENDAR PERIODS
        # =================================================

        if (
            self.days is not None
            or self.months is not None
        ):
            raise ValueError(
                "Calendar periods cannot use "
                "days or months."
            )

        return self


class FilterSpec(StrictModel):
    # Semantic terms.
    #
    # Examples:
    # ["charity"]
    # ["restaurants"]
    # ["automotive"]
    #
    # They will later be resolved through
    # our Concept Registry.
    concepts: list[str] = Field(
        default_factory=list
    )

    merchants: list[str] = Field(
        default_factory=list
    )

    account_ids: list[str] = Field(
        default_factory=list
    )

    financial_natures: list[
        FinancialNature
    ] = Field(
        default_factory=list
    )

    minimum_amount_minor: int | None = Field(
        default=None,
        ge=0,
    )

    maximum_amount_minor: int | None = Field(
        default=None,
        ge=0,
    )

    @model_validator(mode="after")
    def validate_amount_range(self):
        if (
            self.minimum_amount_minor is not None
            and self.maximum_amount_minor is not None
            and self.minimum_amount_minor
            > self.maximum_amount_minor
        ):
            raise ValueError(
                "minimum_amount_minor cannot be greater "
                "than maximum_amount_minor."
            )

        return self


class ComparisonSpec(StrictModel):
    type: ComparisonType

    # Only used when type = custom_period
    period: PeriodSpec | None = None

    @model_validator(mode="after")
    def validate_comparison(self):
        if (
            self.type == ComparisonType.CUSTOM_PERIOD
            and self.period is None
        ):
            raise ValueError(
                "period is required for custom_period."
            )

        return self


class QuerySpec(StrictModel):
    metric: Metric

    period: PeriodSpec

    filters: FilterSpec = Field(
        default_factory=FilterSpec
    )

    group_by: GroupBy | None = None

    comparison: ComparisonSpec | None = None

    sort: SortDirection | None = None

    limit: int | None = Field(
        default=None,
        ge=1,
        le=100,
    )