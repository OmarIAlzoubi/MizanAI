import calendar
import re
import unicodedata

from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    timedelta,
)

from zoneinfo import ZoneInfo

from app.core.config import (
    get_settings,
)


# =========================================================
# ERRORS
# =========================================================


class RecipeParameterResolutionError(
    ValueError
):
    pass


# =========================================================
# PERIOD MODEL
# =========================================================


@dataclass(frozen=True)
class ResolvedPeriod:

    name: str

    requested_start: date

    requested_end: date

    start: date

    end: date

    clipped_by_coverage: bool = False

    def to_dict(
        self,
    ) -> dict:

        return {
            "name":
                self.name,

            "requested_start":
                self.requested_start
                .isoformat(),

            "requested_end":
                self.requested_end
                .isoformat(),

            "start":
                self.start
                .isoformat(),

            "end":
                self.end
                .isoformat(),

            "clipped_by_coverage":
                self.clipped_by_coverage,
        }


# =========================================================
# NORMALIZATION
# =========================================================


_ARABIC_DIACRITICS = re.compile(
    r"[\u0617-\u061A"
    r"\u064B-\u0652"
    r"\u0670"
    r"\u06D6-\u06ED]"
)


def _normalize_text(
    text: str,
) -> str:

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = text.casefold()

    text = (
        _ARABIC_DIACRITICS
        .sub(
            "",
            text,
        )
    )

    text = text.replace(
        "ـ",
        "",
    )

    text = re.sub(
        r"[أإآٱ]",
        "ا",
        text,
    )

    text = text.replace(
        "ى",
        "ي",
    )

    text = text.replace(
        "ؤ",
        "و",
    )

    text = text.replace(
        "ئ",
        "ي",
    )

    text = re.sub(
        r"[^\w\s-]",
        " ",
        text,
        flags=re.UNICODE,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# =========================================================
# DATE HELPERS
# =========================================================


def _previous_month(
    year: int,
    month: int,
) -> tuple[
    int,
    int,
]:

    if month == 1:

        return (
            year - 1,
            12,
        )

    return (
        year,
        month - 1,
    )


def _month_end(
    year: int,
    month: int,
) -> date:

    last_day = (
        calendar.monthrange(
            year,
            month,
        )[1]
    )

    return date(
        year,
        month,
        last_day,
    )


# =========================================================
# RESOLVER
# =========================================================


class RecipePeriodResolver:

    def __init__(
        self,
    ):

        self.settings = (
            get_settings()
        )

        self.timezone = ZoneInfo(
            self.settings
            .default_timezone
        )

        # Python:
        # Monday = 0
        # Sunday = 6
        #
        # MizanAI's preferred week start is Sunday.
        self.week_start = getattr(
            self.settings,
            "default_week_start",
            6,
        )

    # =====================================================
    # NOW
    # =====================================================

    def local_now(
        self,
    ) -> datetime:

        return datetime.now(
            self.timezone
        )

    # =====================================================
    # TARGET PERIOD
    # =====================================================

    def resolve_target_period(
        self,
        *,
        message: str,
        now: datetime | None = None,
    ) -> ResolvedPeriod:

        message = (
            message.strip()
        )

        if not message:

            raise (
                RecipeParameterResolutionError(
                    "Message cannot be empty."
                )
            )

        now = (
            now
            or self.local_now()
        )

        today = (
            now.astimezone(
                self.timezone
            )
            .date()
        )

        text = (
            _normalize_text(
                message
            )
        )

        # =============================================
        # CURRENT MONTH
        # =============================================

        current_month_patterns = (
            "هذا الشهر",
            "هالشهر",
            "الشهر الحالي",
            "الشهر الجاري",
            "this month",
            "current month",
            "month to date",
            "month-to-date",
            "mtd",
        )

        if any(
            pattern in text
            for pattern
            in current_month_patterns
        ):

            return ResolvedPeriod(
                name="current_month",
                requested_start=date(
                    today.year,
                    today.month,
                    1,
                ),
                requested_end=today,
                start=date(
                    today.year,
                    today.month,
                    1,
                ),
                end=today,
            )

        # =============================================
        # CURRENT MONTH IMPLIED BY COMPARISON
        #
        # "مقارنة بالشهر الماضي"
        # means current month vs last month.
        # =============================================

        comparison_markers = (
            "مقارنه",
            "مقارنة",
            "مقابل",
            "compare",
            "compared",
            "versus",
            " vs ",
        )

        previous_month_markers = (
            "الشهر الماضي",
            "الشهر السابق",
            "last month",
            "previous month",
        )

        if (
            any(
                marker in text
                for marker
                in comparison_markers
            )
            and any(
                marker in text
                for marker
                in previous_month_markers
            )
        ):

            start = date(
                today.year,
                today.month,
                1,
            )

            return ResolvedPeriod(
                name="current_month",
                requested_start=start,
                requested_end=today,
                start=start,
                end=today,
            )

        # =============================================
        # PREVIOUS MONTH
        # =============================================

        if any(
            marker in text
            for marker
            in previous_month_markers
        ):

            year, month = (
                _previous_month(
                    today.year,
                    today.month,
                )
            )

            start = date(
                year,
                month,
                1,
            )

            end = (
                _month_end(
                    year,
                    month,
                )
            )

            return ResolvedPeriod(
                name="previous_month",
                requested_start=start,
                requested_end=end,
                start=start,
                end=end,
            )

        # =============================================
        # CURRENT WEEK
        # =============================================

        current_week_patterns = (
            "هذا الاسبوع",
            "هالاسبوع",
            "الاسبوع الحالي",
            "this week",
            "current week",
            "week to date",
            "week-to-date",
        )

        if any(
            pattern in text
            for pattern
            in current_week_patterns
        ):

            days_since_start = (
                today.weekday()
                - self.week_start
            ) % 7

            start = (
                today
                - timedelta(
                    days=days_since_start
                )
            )

            return ResolvedPeriod(
                name="current_week",
                requested_start=start,
                requested_end=today,
                start=start,
                end=today,
            )

        # =============================================
        # PREVIOUS WEEK
        # =============================================

        previous_week_patterns = (
            "الاسبوع الماضي",
            "الاسبوع السابق",
            "last week",
            "previous week",
        )

        if any(
            pattern in text
            for pattern
            in previous_week_patterns
        ):

            days_since_start = (
                today.weekday()
                - self.week_start
            ) % 7

            current_week_start = (
                today
                - timedelta(
                    days=days_since_start
                )
            )

            start = (
                current_week_start
                - timedelta(
                    days=7
                )
            )

            end = (
                start
                + timedelta(
                    days=6
                )
            )

            return ResolvedPeriod(
                name="previous_week",
                requested_start=start,
                requested_end=end,
                start=start,
                end=end,
            )

        # =============================================
        # TODAY
        # =============================================

        if (
            "اليوم" in text
            or re.search(
                r"\btoday\b",
                text,
            )
        ):

            return ResolvedPeriod(
                name="today",
                requested_start=today,
                requested_end=today,
                start=today,
                end=today,
            )

        # =============================================
        # YESTERDAY
        # =============================================

        if (
            "امس" in text
            or re.search(
                r"\byesterday\b",
                text,
            )
        ):

            yesterday = (
                today
                - timedelta(
                    days=1
                )
            )

            return ResolvedPeriod(
                name="yesterday",
                requested_start=yesterday,
                requested_end=yesterday,
                start=yesterday,
                end=yesterday,
            )

        # =============================================
        # LAST N DAYS
        # =============================================

        match = re.search(
            r"\b(?:اخر|آخر)\s+(\d+)\s+"
            r"(?:يوم|ايام)\b",
            text,
        )

        if match is None:

            match = re.search(
                r"\blast\s+(\d+)\s+days?\b",
                text,
            )

        if match is not None:

            days = int(
                match.group(1)
            )

            if (
                days < 1
                or days > 366
            ):

                raise (
                    RecipeParameterResolutionError(
                        "Unsupported day range."
                    )
                )

            start = (
                today
                - timedelta(
                    days=days - 1
                )
            )

            return ResolvedPeriod(
                name=f"last_{days}_days",
                requested_start=start,
                requested_end=today,
                start=start,
                end=today,
            )

        # =============================================
        # NO SAFE MATCH
        # =============================================

        raise (
            RecipeParameterResolutionError(
                "Could not resolve an explicit "
                "target period from the message."
            )
        )

    # =====================================================
    # COVERAGE CLIPPING
    # =====================================================

    def apply_coverage(
        self,
        *,
        period: ResolvedPeriod,
        coverage_end: date,
    ) -> ResolvedPeriod:

        if (
            coverage_end
            < period.requested_start
        ):

            raise (
                RecipeParameterResolutionError(
                    "Available transaction data ends "
                    "before the requested period starts."
                )
            )

        effective_end = min(
            period.requested_end,
            coverage_end,
        )

        return ResolvedPeriod(
            name=period.name,

            requested_start=(
                period.requested_start
            ),

            requested_end=(
                period.requested_end
            ),

            start=(
                period.requested_start
            ),

            end=(
                effective_end
            ),

            clipped_by_coverage=(
                effective_end
                < period.requested_end
            ),
        )

    # =====================================================
    # SAME ELAPSED PREVIOUS PERIOD
    # =====================================================

    def derive_same_elapsed_previous_period(
        self,
        *,
        target: ResolvedPeriod,
    ) -> ResolvedPeriod:

        # ---------------------------------------------
        # MONTH-BASED PERIOD
        # ---------------------------------------------

        if (
            target.start.day == 1
            and target.start.year
            == target.end.year
            and target.start.month
            == target.end.month
        ):

            previous_year, previous_month = (
                _previous_month(
                    target.start.year,
                    target.start.month,
                )
            )

            previous_last_day = (
                calendar.monthrange(
                    previous_year,
                    previous_month,
                )[1]
            )

            comparable_day = min(
                target.end.day,
                previous_last_day,
            )

            start = date(
                previous_year,
                previous_month,
                1,
            )

            end = date(
                previous_year,
                previous_month,
                comparable_day,
            )

            return ResolvedPeriod(
                name=(
                    "same_elapsed_previous_month"
                ),

                requested_start=start,
                requested_end=end,
                start=start,
                end=end,
            )

        # ---------------------------------------------
        # GENERIC COMPARABLE WINDOW
        #
        # For week / N-day windows:
        # use the immediately preceding window with
        # exactly the same number of covered days.
        # ---------------------------------------------

        duration_days = (
            target.end
            - target.start
        ).days + 1

        end = (
            target.start
            - timedelta(
                days=1
            )
        )

        start = (
            end
            - timedelta(
                days=duration_days - 1
            )
        )

        return ResolvedPeriod(
            name=(
                "same_elapsed_previous_period"
            ),

            requested_start=start,
            requested_end=end,
            start=start,
            end=end,
        )