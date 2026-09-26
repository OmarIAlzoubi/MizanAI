from datetime import timezone

from app.contracts.query_spec import (
    QuerySpec,
)

from app.core.config import (
    get_settings,
)

from app.core.enums import (
    Metric,
)

from app.core.time import (
    resolve_period,
)

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)

from app.modules.analytics.models import (
    FinancialQueryResult,
)

from app.modules.analytics.repository import (
    AnalyticsRepository,
)


class UnsupportedMetricError(Exception):
    pass


class AnalyticsService:

    def __init__(
        self,
        database: Database | None = None,
        repository: AnalyticsRepository | None = None,
    ):
        self.database = (
            database
            or get_default_database()
        )

        self.repository = (
            repository
            or AnalyticsRepository()
        )

        self.settings = (
            get_settings()
        )

    # =====================================================
    # QUERY
    # =====================================================

    def query(
        self,
        query: QuerySpec,
    ) -> FinancialQueryResult:

        # =================================================
        # BALANCE
        #
        # Balance is a point-in-time value.
        # It does not need a date period.
        # =================================================

        if query.metric == Metric.BALANCE:

            with self.database.session() as conn:

                amount_minor = (
                    self.repository
                    .calculate_current_balance(
                        conn=conn
                    )
                )

            return FinancialQueryResult(
                metric=Metric.BALANCE,

                amount_minor=(
                    amount_minor
                ),

                currency=(
                    self.settings
                    .default_currency
                ),

                transaction_count=0,

                period_start_utc=None,

                period_end_utc=None,

                concepts=[],
            )

        # =================================================
        # PERIOD-BASED METRICS
        # =================================================

        resolved = resolve_period(
            query.period,

            timezone_name=(
                self.settings
                .default_timezone
            ),

            week_start=(
                self.settings
                .default_week_start
            ),
        )

        start_utc = (
            resolved.start
            .astimezone(
                timezone.utc
            )
        )

        end_utc = (
            resolved.end
            .astimezone(
                timezone.utc
            )
        )

        # =================================================
        # SPENDING
        # =================================================

        if query.metric == Metric.SPENDING:

            with self.database.session() as conn:

                (
                    amount_minor,
                    transaction_count,
                ) = (
                    self.repository
                    .calculate_spending(
                        conn=conn,
                        query=query,
                        start_utc=start_utc,
                        end_utc=end_utc,
                    )
                )

            return FinancialQueryResult(
                metric=(
                    query.metric
                ),

                amount_minor=(
                    amount_minor
                ),

                currency=(
                    self.settings
                    .default_currency
                ),

                transaction_count=(
                    transaction_count
                ),

                period_start_utc=(
                    start_utc
                ),

                period_end_utc=(
                    end_utc
                ),

                concepts=(
                    query
                    .filters
                    .concepts
                ),
            )

        # =================================================
        # UNSUPPORTED
        # =================================================

        raise UnsupportedMetricError(
            f"Metric is not implemented yet: "
            f"{query.metric.value}"
        )