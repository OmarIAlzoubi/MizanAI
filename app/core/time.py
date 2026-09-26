from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time,
    timedelta,
)
from zoneinfo import ZoneInfo

from app.contracts.action_plan import (
    TransactionDateSpec,
)
from app.contracts.query_spec import (
    PeriodSpec,
)
from app.core.config import get_settings
from app.core.enums import (
    PeriodType,
    TransactionDateType,
)


# =========================================================
# RESULT MODEL
# =========================================================

@dataclass(frozen=True)
class ResolvedPeriod:
    """
    Half-open time range:

        start <= timestamp < end
    """

    start: datetime
    end: datetime


# =========================================================
# HELPERS
# =========================================================

def _local_midnight(
    value: date,
    timezone_name: str,
) -> datetime:

    tz = ZoneInfo(
        timezone_name
    )

    return datetime.combine(
        value,
        time.min,
        tzinfo=tz,
    )


def _normalize_now(
    *,
    timezone_name: str,
    now: datetime | None,
) -> datetime:

    tz = ZoneInfo(
        timezone_name
    )

    if now is None:
        return datetime.now(
            tz
        )

    if now.tzinfo is None:
        return now.replace(
            tzinfo=tz
        )

    return now.astimezone(
        tz
    )


def _shift_month(
    year: int,
    month: int,
    offset: int,
) -> tuple[int, int]:

    """
    Example:

    2026, 9, 0
    -> 2026, 9

    2026, 9, -1
    -> 2026, 8

    2026, 12, 1
    -> 2027, 1
    """

    total_months = (
        year * 12
        + (month - 1)
        + offset
    )

    shifted_year = (
        total_months // 12
    )

    shifted_month = (
        total_months % 12
        + 1
    )

    return (
        shifted_year,
        shifted_month,
    )


# =========================================================
# TRANSACTION DATE
# =========================================================

def resolve_transaction_date(
    spec: TransactionDateSpec,
    *,
    timezone_name: str | None = None,
    now: datetime | None = None,
) -> datetime:

    settings = get_settings()

    timezone_name = (
        timezone_name
        or settings.default_timezone
    )

    local_now = _normalize_now(
        timezone_name=timezone_name,
        now=now,
    )

    # ---------------------------------
    # RELATIVE CALENDAR DAY
    # ---------------------------------

    if (
        spec.type
        == TransactionDateType.CALENDAR_DAY
    ):
        target_date = (
            local_now.date()
            + timedelta(
                days=spec.offset
            )
        )

        return _local_midnight(
            target_date,
            timezone_name,
        )

    # ---------------------------------
    # EXACT DATE
    # ---------------------------------

    if (
        spec.type
        == TransactionDateType.EXACT_DATE
    ):
        if spec.date is None:
            raise ValueError(
                "exact_date requires a date."
            )

        return _local_midnight(
            spec.date,
            timezone_name,
        )

    raise ValueError(
        "Unsupported transaction date type: "
        f"{spec.type}"
    )


# =========================================================
# QUERY PERIOD
# =========================================================

def resolve_period(
    spec: PeriodSpec,
    *,
    timezone_name: str | None = None,
    week_start: int | None = None,
    now: datetime | None = None,
) -> ResolvedPeriod:

    settings = get_settings()

    timezone_name = (
        timezone_name
        or settings.default_timezone
    )

    if week_start is None:
        week_start = (
            settings.default_week_start
        )

    if week_start not in range(7):
        raise ValueError(
            "week_start must be between 0 and 6."
        )

    local_now = _normalize_now(
        timezone_name=timezone_name,
        now=now,
    )

    today = local_now.date()

    # =====================================================
    # EXPLICIT DATE RANGE OVERRIDE
    # =====================================================
    #
    # If explicit dates are present, they are authoritative
    # regardless of the semantic period type that came with
    # them from the understanding layer.
    #
    # Example:
    #
    #   type=calendar_day
    #   offset=0
    #   start_date=2026-09-10
    #   end_date=2026-09-10
    #
    # must resolve to Sep 10, not "today".
    #
    # The user's end_date is inclusive, while the internal
    # query interval is half-open:
    #
    #   start <= timestamp < end
    #
    # so 2026-09-10 .. 2026-09-10 becomes:
    #
    #   [2026-09-10 00:00, 2026-09-11 00:00)
    # =====================================================

    has_start_date = (
        spec.start_date
        is not None
    )

    has_end_date = (
        spec.end_date
        is not None
    )

    if (
        has_start_date
        or has_end_date
    ):
        if not (
            has_start_date
            and has_end_date
        ):
            raise ValueError(
                "Explicit query periods require "
                "both start_date and end_date."
            )

        if (
            spec.end_date
            < spec.start_date
        ):
            raise ValueError(
                "end_date cannot be before "
                "start_date."
            )

        exclusive_end = (
            spec.end_date
            + timedelta(days=1)
        )

        return ResolvedPeriod(
            start=_local_midnight(
                spec.start_date,
                timezone_name,
            ),
            end=_local_midnight(
                exclusive_end,
                timezone_name,
            ),
        )

    # =====================================================
    # CALENDAR DAY
    # =====================================================

    if (
        spec.type
        == PeriodType.CALENDAR_DAY
    ):
        target = (
            today
            + timedelta(
                days=spec.offset
            )
        )

        start = _local_midnight(
            target,
            timezone_name,
        )

        end = _local_midnight(
            target
            + timedelta(days=1),
            timezone_name,
        )

        return ResolvedPeriod(
            start=start,
            end=end,
        )

    # =====================================================
    # CALENDAR WEEK
    # =====================================================

    if (
        spec.type
        == PeriodType.CALENDAR_WEEK
    ):
        # Python:
        # Monday = 0
        # ...
        # Sunday = 6

        days_since_week_start = (
            today.weekday()
            - week_start
        ) % 7

        current_week_start = (
            today
            - timedelta(
                days=days_since_week_start
            )
        )

        target_week_start = (
            current_week_start
            + timedelta(
                weeks=spec.offset
            )
        )

        target_week_end = (
            target_week_start
            + timedelta(days=7)
        )

        return ResolvedPeriod(
            start=_local_midnight(
                target_week_start,
                timezone_name,
            ),
            end=_local_midnight(
                target_week_end,
                timezone_name,
            ),
        )

    # =====================================================
    # CALENDAR MONTH
    # =====================================================

    if (
        spec.type
        == PeriodType.CALENDAR_MONTH
    ):
        target_year, target_month = (
            _shift_month(
                local_now.year,
                local_now.month,
                spec.offset,
            )
        )

        next_year, next_month = (
            _shift_month(
                target_year,
                target_month,
                1,
            )
        )

        start_date = date(
            target_year,
            target_month,
            1,
        )

        end_date = date(
            next_year,
            next_month,
            1,
        )

        return ResolvedPeriod(
            start=_local_midnight(
                start_date,
                timezone_name,
            ),
            end=_local_midnight(
                end_date,
                timezone_name,
            ),
        )

    # =====================================================
    # CALENDAR YEAR
    # =====================================================

    if (
        spec.type
        == PeriodType.CALENDAR_YEAR
    ):
        target_year = (
            local_now.year
            + spec.offset
        )

        start_date = date(
            target_year,
            1,
            1,
        )

        end_date = date(
            target_year + 1,
            1,
            1,
        )

        return ResolvedPeriod(
            start=_local_midnight(
                start_date,
                timezone_name,
            ),
            end=_local_midnight(
                end_date,
                timezone_name,
            ),
        )

    # =====================================================
    # ROLLING DAYS
    # =====================================================

    if (
        spec.type
        == PeriodType.ROLLING_DAYS
    ):
        if spec.days is None:
            raise ValueError(
                "rolling_days requires days."
            )

        # Include today as a complete calendar day
        # range ending at tomorrow midnight.

        end_date = (
            today
            + timedelta(days=1)
        )

        start_date = (
            end_date
            - timedelta(
                days=spec.days
            )
        )

        return ResolvedPeriod(
            start=_local_midnight(
                start_date,
                timezone_name,
            ),
            end=_local_midnight(
                end_date,
                timezone_name,
            ),
        )

    # =====================================================
    # ROLLING MONTHS
    # =====================================================

    if (
        spec.type
        == PeriodType.ROLLING_MONTHS
    ):
        if spec.months is None:
            raise ValueError(
                "rolling_months requires months."
            )

        # Current calendar month is included.

        end_year, end_month = (
            _shift_month(
                local_now.year,
                local_now.month,
                1,
            )
        )

        start_year, start_month = (
            _shift_month(
                end_year,
                end_month,
                -spec.months,
            )
        )

        start_date = date(
            start_year,
            start_month,
            1,
        )

        end_date = date(
            end_year,
            end_month,
            1,
        )

        return ResolvedPeriod(
            start=_local_midnight(
                start_date,
                timezone_name,
            ),
            end=_local_midnight(
                end_date,
                timezone_name,
            ),
        )

    # =====================================================
    # ABSOLUTE RANGE
    # =====================================================

    if (
        spec.type
        == PeriodType.ABSOLUTE_RANGE
    ):
        if (
            spec.start_date is None
            or spec.end_date is None
        ):
            raise ValueError(
                "absolute_range requires "
                "start_date and end_date."
            )

        if (
            spec.end_date
            < spec.start_date
        ):
            raise ValueError(
                "end_date cannot be before "
                "start_date."
            )

        # User range is inclusive:
        #
        # Sep 1 -> Sep 10
        #
        # Database range:
        #
        # >= Sep 1 00:00
        # <  Sep 11 00:00

        exclusive_end = (
            spec.end_date
            + timedelta(days=1)
        )

        return ResolvedPeriod(
            start=_local_midnight(
                spec.start_date,
                timezone_name,
            ),
            end=_local_midnight(
                exclusive_end,
                timezone_name,
            ),
        )

    raise ValueError(
        "Unsupported period type: "
        f"{spec.type}"
    )