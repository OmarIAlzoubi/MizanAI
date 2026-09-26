from datetime import (
    datetime,
    timedelta,
    timezone,
)

from app.contracts.query_spec import (
    PeriodSpec,
)

from app.core.config import (
    get_settings,
)

from app.core.enums import (
    PeriodType,
)

from app.core.time import (
    resolve_period,
)

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)

from app.infrastructure.database.state import (
    get_state,
)

from app.modules.analytics.dashboard_models import (
    CategorySpendingPoint,
    DashboardSummary,
    MonthlySpendingPoint,
)

from app.modules.analytics.dashboard_repository import (
    DashboardRepository,
)


class DashboardService:

    def __init__(
        self,
        database: Database | None = None,
        repository: DashboardRepository | None = None,
    ):

        self.database = (
            database
            or get_default_database()
        )

        self.repository = (
            repository
            or DashboardRepository()
        )

        self.settings = (
            get_settings()
        )

    # =====================================================
    # PUBLIC
    # =====================================================

    def get_summary(
        self,
    ) -> DashboardSummary:

        # =============================================
        # CURRENT MONTH
        # =============================================

        current_period = (
            resolve_period(
                PeriodSpec(
                    type=(
                        PeriodType
                        .CALENDAR_MONTH
                    ),
                    offset=0,
                ),
                timezone_name=(
                    self.settings
                    .default_timezone
                ),
                week_start=(
                    self.settings
                    .default_week_start
                ),
            )
        )

        # =============================================
        # PREVIOUS MONTH
        # =============================================

        previous_period = (
            resolve_period(
                PeriodSpec(
                    type=(
                        PeriodType
                        .CALENDAR_MONTH
                    ),
                    offset=-1,
                ),
                timezone_name=(
                    self.settings
                    .default_timezone
                ),
                week_start=(
                    self.settings
                    .default_week_start
                ),
            )
        )

        # =============================================
        # UTC BOUNDARIES
        # =============================================

        current_start_utc = (
            current_period.start
            .astimezone(
                timezone.utc
            )
        )

        current_end_utc = (
            current_period.end
            .astimezone(
                timezone.utc
            )
        )

        previous_start_utc = (
            previous_period.start
            .astimezone(
                timezone.utc
            )
        )

        # =============================================
        # DATABASE
        # =============================================

        with self.database.session() as conn:

            # =========================================
            # CURRENT BALANCE
            # =========================================

            balance_anchor_minor = (
                get_state(
                    conn,
                    "balance_anchor_minor",
                )
            )

            balance_anchor_utc = (
                get_state(
                    conn,
                    "balance_anchor_utc",
                )
            )

            if (
                balance_anchor_minor is None
                or balance_anchor_utc is None
            ):
                raise RuntimeError(
                    "Balance anchor is not configured."
                )

            anchor_balance = int(
                balance_anchor_minor
            )

            anchor_datetime = (
                datetime.fromisoformat(
                    balance_anchor_utc
                )
            )

            net_flow = (
                self.repository
                .net_flow_after(
                    conn=conn,
                    anchor_utc=(
                        anchor_datetime
                    ),
                )
            )

            current_balance = (
                anchor_balance
                + net_flow
            )

            # =========================================
            # LATEST AVAILABLE DATA DATE
            # =========================================

            latest_transaction_utc = (
                self.repository
                .latest_transaction_time(
                    conn=conn
                )
            )

            if latest_transaction_utc:

                latest_local = (
                    latest_transaction_utc
                    .astimezone(
                        current_period
                        .start
                        .tzinfo
                    )
                )

                comparison_day = (
                    latest_local.day
                )

            else:

                comparison_day = (
                    datetime.now(
                        current_period
                        .start
                        .tzinfo
                    ).day
                )

            # =========================================
            # CURRENT MONTH SPENDING
            # =========================================

            current_spending = (
                self.repository
                .spending_between(
                    conn=conn,
                    start_utc=(
                        current_start_utc
                    ),
                    end_utc=(
                        current_end_utc
                    ),
                )
            )

            # =========================================
            # PREVIOUS MONTH:
            # SAME NUMBER OF DAYS
            # =========================================

            previous_comparison_end_local = (
                previous_period.start
                + timedelta(
                    days=comparison_day
                )
            )

            if (
                previous_comparison_end_local
                > previous_period.end
            ):
                previous_comparison_end_local = (
                    previous_period.end
                )

            previous_comparison_end_utc = (
                previous_comparison_end_local
                .astimezone(
                    timezone.utc
                )
            )

            previous_spending = (
                self.repository
                .spending_between(
                    conn=conn,
                    start_utc=(
                        previous_start_utc
                    ),
                    end_utc=(
                        previous_comparison_end_utc
                    ),
                )
            )

            # =========================================
            # MONTHLY TREND
            # =========================================

            monthly_spending = []

            for offset in (
                -2,
                -1,
                0,
            ):

                period = (
                    resolve_period(
                        PeriodSpec(
                            type=(
                                PeriodType
                                .CALENDAR_MONTH
                            ),
                            offset=offset,
                        ),
                        timezone_name=(
                            self.settings
                            .default_timezone
                        ),
                        week_start=(
                            self.settings
                            .default_week_start
                        ),
                    )
                )

                period_start_utc = (
                    period.start
                    .astimezone(
                        timezone.utc
                    )
                )

                period_end_utc = (
                    period.end
                    .astimezone(
                        timezone.utc
                    )
                )

                amount_minor = (
                    self.repository
                    .spending_between(
                        conn=conn,
                        start_utc=(
                            period_start_utc
                        ),
                        end_utc=(
                            period_end_utc
                        ),
                    )
                )

                monthly_spending.append(
                    MonthlySpendingPoint(
                        month=(
                            period.start
                            .strftime(
                                "%Y-%m"
                            )
                        ),
                        amount_minor=(
                            amount_minor
                        ),
                    )
                )

            # =========================================
            # TOP CATEGORIES
            # =========================================

            category_rows = (
                self.repository
                .top_categories(
                    conn=conn,
                    start_utc=(
                        current_start_utc
                    ),
                    end_utc=(
                        current_end_utc
                    ),
                    limit=5,
                )
            )

        # =============================================
        # CATEGORY MODELS
        # =============================================

        top_categories = [

            CategorySpendingPoint(
                concept=(
                    row["concept"]
                ),
                amount_minor=int(
                    row["amount_minor"]
                    or 0
                ),
            )

            for row
            in category_rows

        ]

        # =============================================
        # CHANGE
        # =============================================

        change_percent = (
            self._change_percent(
                current=(
                    current_spending
                ),
                previous=(
                    previous_spending
                ),
            )
        )

        # =============================================
        # INSIGHT
        # =============================================

        insight = (
            self._build_insight(
                current=(
                    current_spending
                ),
                previous=(
                    previous_spending
                ),
                change_percent=(
                    change_percent
                ),
            )
        )

        # =============================================
        # RESULT
        # =============================================

        return DashboardSummary(

            current_balance_minor=(
                current_balance
            ),

            current_month_spending_minor=(
                current_spending
            ),

            previous_month_spending_minor=(
                previous_spending
            ),

            change_percent=(
                change_percent
            ),

            monthly_spending=(
                monthly_spending
            ),

            top_categories=(
                top_categories
            ),

            insight=(
                insight
            ),
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @staticmethod
    def _change_percent(
        *,
        current: int,
        previous: int,
    ) -> float | None:

        if previous == 0:
            return None

        value = (
            (
                current
                - previous
            )
            / previous
        ) * 100

        return round(
            value,
            1,
        )

    @staticmethod
    def _build_insight(
        *,
        current: int,
        previous: int,
        change_percent: float | None,
    ) -> str:

        if change_percent is None:

            return (
                "لا توجد بيانات كافية "
                "للمقارنة مع الشهر الماضي."
            )

        if change_percent > 0:

            return (
                "إنفاقك هذا الشهر أعلى "
                f"بنسبة "
                f"{abs(change_percent):.1f}% "
                "من نفس الفترة "
                "في الشهر الماضي."
            )

        if change_percent < 0:

            return (
                "إنفاقك هذا الشهر أقل "
                f"بنسبة "
                f"{abs(change_percent):.1f}% "
                "من نفس الفترة "
                "في الشهر الماضي."
            )

        return (
            "إنفاقك مماثل "
            "لنفس الفترة "
            "في الشهر الماضي."
        )