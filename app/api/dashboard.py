from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import (
    date,
    datetime,
    time,
    timedelta,
    timezone,
)
from zoneinfo import ZoneInfo

from app.core.config import (
    get_settings,
)
from app.infrastructure.database.connection import (
    get_default_database,
)


EXPENSE_WHERE = """
status = 'posted'
AND direction = 'debit'
AND financial_nature = 'expense'
"""


def _parse_datetime(
    value: str | None,
) -> datetime | None:

    if not value:
        return None

    normalized = (
        value.replace(
            "Z",
            "+00:00",
        )
    )

    parsed = datetime.fromisoformat(
        normalized
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _utc_bounds(
    *,
    start_date: date,
    end_date: date,
    timezone_name: str,
) -> tuple[str, str]:

    tz = ZoneInfo(
        timezone_name
    )

    start_local = datetime.combine(
        start_date,
        time.min,
        tzinfo=tz,
    )

    end_local = datetime.combine(
        end_date
        + timedelta(days=1),
        time.min,
        tzinfo=tz,
    )

    start_utc = (
        start_local
        .astimezone(
            timezone.utc
        )
        .isoformat()
    )

    end_utc = (
        end_local
        .astimezone(
            timezone.utc
        )
        .isoformat()
    )

    return (
        start_utc,
        end_utc,
    )


def _previous_month_same_elapsed(
    coverage_end: date,
) -> tuple[date, date]:

    if coverage_end.month == 1:
        year = (
            coverage_end.year - 1
        )

        month = 12

    else:
        year = coverage_end.year

        month = (
            coverage_end.month - 1
        )

    start = date(
        year,
        month,
        1,
    )

    last_day = monthrange(
        year,
        month,
    )[1]

    end = date(
        year,
        month,
        min(
            coverage_end.day,
            last_day,
        ),
    )

    return (
        start,
        end,
    )


def _aggregate_daily(
    *,
    rows,
    start_date: date,
    end_date: date,
    timezone_name: str,
) -> list[dict]:

    tz = ZoneInfo(
        timezone_name
    )

    totals: dict[
        date,
        int,
    ] = defaultdict(
        int
    )

    for row in rows:

        occurred = _parse_datetime(
            row[
                "occurred_at_utc"
            ]
        )

        if occurred is None:
            continue

        local_date = (
            occurred
            .astimezone(
                tz
            )
            .date()
        )

        totals[
            local_date
        ] += int(
            row[
                "amount_minor"
            ]
        )

    result = []

    cursor = start_date

    while cursor <= end_date:

        result.append(
            {
                "date":
                    cursor.isoformat(),

                "amount_minor":
                    totals.get(
                        cursor,
                        0,
                    ),
            }
        )

        cursor += timedelta(
            days=1
        )

    return result



def _shift_month(
    anchor_date: date,
    offset: int,
) -> tuple[int, int]:

    total_months = (
        anchor_date.year * 12
        + anchor_date.month - 1
        + offset
    )

    year = total_months // 12
    month = total_months % 12 + 1

    return year, month


def _monthly_same_elapsed(
    conn,
    *,
    coverage_start: date | None,
    coverage_end: date,
    timezone_name: str,
    months: int = 4,
) -> list[dict]:

    result = []

    for offset in range(
        -(months - 1),
        1,
    ):

        year, month = _shift_month(
            coverage_end,
            offset,
        )

        month_start = date(
            year,
            month,
            1,
        )

        last_day = monthrange(
            year,
            month,
        )[1]

        month_end = date(
            year,
            month,
            min(
                coverage_end.day,
                last_day,
            ),
        )

        if (
            coverage_start is not None
            and month_end < coverage_start
        ):
            continue

        effective_start = (
            max(
                month_start,
                coverage_start,
            )
            if coverage_start is not None
            else month_start
        )

        effective_end = month_end

        if effective_start > effective_end:
            continue

        start_utc, end_utc = _utc_bounds(
            start_date=effective_start,
            end_date=effective_end,
            timezone_name=timezone_name,
        )

        row = (
            conn.execute(
                f"""
                SELECT
                    COALESCE(
                        SUM(amount_minor),
                        0
                    ) AS amount_minor,

                    COUNT(*) AS transaction_count

                FROM v_financial_transactions

                WHERE
                    {EXPENSE_WHERE}

                    AND occurred_at_utc >= ?
                    AND occurred_at_utc < ?
                """,
                (
                    start_utc,
                    end_utc,
                ),
            )
            .fetchone()
        )

        result.append(
            {
                "month":
                    f"{year:04d}-{month:02d}",

                "start_date":
                    effective_start.isoformat(),

                "end_date":
                    effective_end.isoformat(),

                "amount_minor":
                    int(
                        row["amount_minor"]
                        or 0
                    ),

                "transaction_count":
                    int(
                        row["transaction_count"]
                        or 0
                    ),
            }
        )

    return result


def _concept_widget_summary(
    conn,
    *,
    concept: str,
    start_utc: str,
    end_utc: str,
) -> dict:

    summary = (
        conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(amount_minor),
                    0
                ) AS amount_minor,

                COUNT(
                    DISTINCT transaction_id
                ) AS transaction_count,

                COALESCE(
                    ROUND(
                        AVG(amount_minor)
                    ),
                    0
                ) AS average_transaction_minor

            FROM v_financial_concepts

            WHERE
                status = 'posted'
                AND direction = 'debit'
                AND financial_nature = 'expense'
                AND concept = ?
                AND occurred_at_utc >= ?
                AND occurred_at_utc < ?
            """,
            (
                concept,
                start_utc,
                end_utc,
            ),
        )
        .fetchone()
    )

    top_merchants = [
        {
            "merchant":
                row["merchant"],

            "amount_minor":
                int(
                    row["amount_minor"]
                    or 0
                ),

            "transaction_count":
                int(
                    row["transaction_count"]
                    or 0
                ),
        }
        for row in conn.execute(
            """
            SELECT
                COALESCE(
                    NULLIF(
                        TRIM(merchant),
                        ''
                    ),
                    'غير معروف'
                ) AS merchant,

                SUM(amount_minor)
                    AS amount_minor,

                COUNT(
                    DISTINCT transaction_id
                ) AS transaction_count

            FROM v_financial_concepts

            WHERE
                status = 'posted'
                AND direction = 'debit'
                AND financial_nature = 'expense'
                AND concept = ?
                AND occurred_at_utc >= ?
                AND occurred_at_utc < ?

            GROUP BY
                COALESCE(
                    NULLIF(
                        TRIM(merchant),
                        ''
                    ),
                    'غير معروف'
                )

            ORDER BY
                amount_minor DESC

            LIMIT 3
            """,
            (
                concept,
                start_utc,
                end_utc,
            ),
        )
        .fetchall()
    ]

    return {
        "amount_minor":
            int(
                summary["amount_minor"]
                or 0
            ),

        "transaction_count":
            int(
                summary["transaction_count"]
                or 0
            ),

        "average_transaction_minor":
            int(
                summary[
                    "average_transaction_minor"
                ]
                or 0
            ),

        "top_merchants":
            top_merchants,
    }


def _largest_transactions(
    conn,
    *,
    start_utc: str,
    end_utc: str,
    timezone_name: str,
    limit: int = 4,
) -> list[dict]:

    tz = ZoneInfo(
        timezone_name
    )

    rows = (
        conn.execute(
            f"""
            SELECT
                transaction_id,
                merchant,
                description,
                amount_minor,
                occurred_at_utc

            FROM v_financial_transactions

            WHERE
                {EXPENSE_WHERE}

                AND occurred_at_utc >= ?
                AND occurred_at_utc < ?

            ORDER BY
                amount_minor DESC,
                occurred_at_utc DESC

            LIMIT ?
            """,
            (
                start_utc,
                end_utc,
                limit,
            ),
        )
        .fetchall()
    )

    result = []

    for row in rows:

        occurred = _parse_datetime(
            row["occurred_at_utc"]
        )

        local_date = (
            occurred
            .astimezone(tz)
            .date()
            .isoformat()
            if occurred is not None
            else None
        )

        result.append(
            {
                "transaction_id":
                    row["transaction_id"],

                "merchant":
                    (
                        row["merchant"]
                        or "غير معروف"
                    ),

                "description":
                    row["description"],

                "amount_minor":
                    int(
                        row["amount_minor"]
                        or 0
                    ),

                "occurred_at_utc":
                    row["occurred_at_utc"],

                "local_date":
                    local_date,
            }
        )

    return result

def _empty_dashboard(
    *,
    currency: str,
    balance_minor: int | None,
) -> dict:

    return {
        "period": {
            "start_date":
                None,

            "end_date":
                None,

            "coverage_start_date":
                None,

            "coverage_end_date":
                None,
        },

        "balance": {
            "amount_minor":
                balance_minor,

            "currency":
                currency,
        },

        "spending": {
            "amount_minor":
                0,

            "transaction_count":
                0,

            "average_transaction_minor":
                0,

            "largest_transaction_minor":
                0,

            "previous_same_elapsed_minor":
                0,

            "delta_minor":
                0,

            "daily":
                [],
        },

        "last_7_days":
            [],

        "top_merchants":
            [],

        "top_concepts":
            [],

        "cash_flow": {
            "inflow_minor":
                0,

            "outflow_minor":
                0,

            "net_minor":
                0,
        },

        "monthly_comparison":
            [],

        "bnpl": {
            "amount_minor":
                0,

            "transaction_count":
                0,

            "average_transaction_minor":
                0,

            "top_merchants":
                [],
        },

        "coffee": {
            "amount_minor":
                0,

            "transaction_count":
                0,

            "average_transaction_minor":
                0,

            "top_merchants":
                [],
        },

        "largest_transactions":
            [],
    }


def get_dashboard() -> dict:

    settings = get_settings()

    timezone_name = (
        settings.default_timezone
    )

    default_currency = (
        settings.default_currency
    )

    database = (
        get_default_database()
    )


    with database.session() as conn:

        snapshot = (
            conn.execute(
                """
                SELECT
                    current_balance_minor,
                    currency,
                    latest_transaction_utc
                FROM v_financial_snapshot
                LIMIT 1
                """
            )
            .fetchone()
        )


        balance_minor = (
            snapshot[
                "current_balance_minor"
            ]
            if snapshot is not None
            else None
        )


        currency = (
            snapshot[
                "currency"
            ]
            if (
                snapshot is not None
                and snapshot[
                    "currency"
                ]
            )
            else default_currency
        )


        latest_utc = (
            _parse_datetime(
                snapshot[
                    "latest_transaction_utc"
                ]
            )
            if snapshot is not None
            else None
        )


        earliest_raw = (
            conn.execute(
                """
                SELECT
                    MIN(
                        occurred_at_utc
                    )
                        AS earliest_transaction_utc
                FROM v_financial_transactions
                WHERE status = 'posted'
                """
            )
            .fetchone()
        )


        earliest_utc = (
            _parse_datetime(
                earliest_raw[
                    "earliest_transaction_utc"
                ]
            )
            if earliest_raw is not None
            else None
        )


        if latest_utc is None:

            return _empty_dashboard(
                currency=currency,
                balance_minor=(
                    balance_minor
                ),
            )


        tz = ZoneInfo(
            timezone_name
        )


        coverage_end = (
            latest_utc
            .astimezone(
                tz
            )
            .date()
        )


        coverage_start = (
            earliest_utc
            .astimezone(
                tz
            )
            .date()
            if earliest_utc is not None
            else None
        )


        month_start = date(
            coverage_end.year,
            coverage_end.month,
            1,
        )


        current_start_utc, current_end_utc = (
            _utc_bounds(
                start_date=month_start,
                end_date=coverage_end,
                timezone_name=timezone_name,
            )
        )


        (
            previous_start,
            previous_end,
        ) = (
            _previous_month_same_elapsed(
                coverage_end
            )
        )


        (
            previous_start_utc,
            previous_end_utc,
        ) = (
            _utc_bounds(
                start_date=(
                    previous_start
                ),
                end_date=(
                    previous_end
                ),
                timezone_name=(
                    timezone_name
                ),
            )
        )


        spending = (
            conn.execute(
                f"""
                SELECT
                    COALESCE(
                        SUM(amount_minor),
                        0
                    )
                        AS amount_minor,

                    COUNT(*)
                        AS transaction_count,

                    COALESCE(
                        ROUND(
                            AVG(
                                amount_minor
                            )
                        ),
                        0
                    )
                        AS average_transaction_minor,

                    COALESCE(
                        MAX(
                            amount_minor
                        ),
                        0
                    )
                        AS largest_transaction_minor

                FROM v_financial_transactions

                WHERE
                    {EXPENSE_WHERE}

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?
                """,
                (
                    current_start_utc,
                    current_end_utc,
                ),
            )
            .fetchone()
        )


        previous_spending = (
            conn.execute(
                f"""
                SELECT
                    COALESCE(
                        SUM(amount_minor),
                        0
                    )
                        AS amount_minor

                FROM v_financial_transactions

                WHERE
                    {EXPENSE_WHERE}

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?
                """,
                (
                    previous_start_utc,
                    previous_end_utc,
                ),
            )
            .fetchone()
        )


        current_amount = int(
            spending[
                "amount_minor"
            ]
            or 0
        )


        previous_amount = int(
            previous_spending[
                "amount_minor"
            ]
            or 0
        )


        month_rows = (
            conn.execute(
                f"""
                SELECT
                    occurred_at_utc,
                    amount_minor

                FROM v_financial_transactions

                WHERE
                    {EXPENSE_WHERE}

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?

                ORDER BY
                    occurred_at_utc
                """,
                (
                    current_start_utc,
                    current_end_utc,
                ),
            )
            .fetchall()
        )


        month_daily = (
            _aggregate_daily(
                rows=month_rows,
                start_date=month_start,
                end_date=coverage_end,
                timezone_name=(
                    timezone_name
                ),
            )
        )


        last_7_start = (
            coverage_end
            - timedelta(
                days=6
            )
        )


        (
            last_7_start_utc,
            last_7_end_utc,
        ) = (
            _utc_bounds(
                start_date=(
                    last_7_start
                ),
                end_date=(
                    coverage_end
                ),
                timezone_name=(
                    timezone_name
                ),
            )
        )


        last_7_rows = (
            conn.execute(
                f"""
                SELECT
                    occurred_at_utc,
                    amount_minor

                FROM v_financial_transactions

                WHERE
                    {EXPENSE_WHERE}

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?

                ORDER BY
                    occurred_at_utc
                """,
                (
                    last_7_start_utc,
                    last_7_end_utc,
                ),
            )
            .fetchall()
        )


        last_7_days = (
            _aggregate_daily(
                rows=last_7_rows,
                start_date=(
                    last_7_start
                ),
                end_date=(
                    coverage_end
                ),
                timezone_name=(
                    timezone_name
                ),
            )
        )


        top_merchants = [
            {
                "merchant":
                    row[
                        "merchant"
                    ],

                "amount_minor":
                    int(
                        row[
                            "amount_minor"
                        ]
                        or 0
                    ),

                "transaction_count":
                    int(
                        row[
                            "transaction_count"
                        ]
                        or 0
                    ),
            }

            for row in conn.execute(
                f"""
                SELECT
                    COALESCE(
                        NULLIF(
                            TRIM(
                                merchant
                            ),
                            ''
                        ),
                        'غير معروف'
                    )
                        AS merchant,

                    SUM(
                        amount_minor
                    )
                        AS amount_minor,

                    COUNT(*)
                        AS transaction_count

                FROM v_financial_transactions

                WHERE
                    {EXPENSE_WHERE}

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?

                GROUP BY
                    COALESCE(
                        NULLIF(
                            TRIM(
                                merchant
                            ),
                            ''
                        ),
                        'غير معروف'
                    )

                ORDER BY
                    amount_minor DESC

                LIMIT 4
                """,
                (
                    current_start_utc,
                    current_end_utc,
                ),
            )
            .fetchall()
        ]


        top_concepts = [
            {
                "concept":
                    row[
                        "concept"
                    ],

                "amount_minor":
                    int(
                        row[
                            "amount_minor"
                        ]
                        or 0
                    ),

                "transaction_count":
                    int(
                        row[
                            "transaction_count"
                        ]
                        or 0
                    ),
            }

            for row in conn.execute(
                """
                SELECT
                    concept,

                    SUM(
                        amount_minor
                    )
                        AS amount_minor,

                    COUNT(
                        DISTINCT
                        transaction_id
                    )
                        AS transaction_count

                FROM v_financial_concepts

                WHERE
                    status = 'posted'

                    AND
                    direction = 'debit'

                    AND
                    financial_nature = 'expense'

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?

                GROUP BY
                    concept

                ORDER BY
                    amount_minor DESC

                LIMIT 4
                """,
                (
                    current_start_utc,
                    current_end_utc,
                ),
            )
            .fetchall()
        ]


        cash_flow = (
            conn.execute(
                """
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN direction = 'credit'
                                THEN amount_minor
                                ELSE 0
                            END
                        ),
                        0
                    )
                        AS inflow_minor,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN direction = 'debit'
                                THEN amount_minor
                                ELSE 0
                            END
                        ),
                        0
                    )
                        AS outflow_minor

                FROM v_financial_transactions

                WHERE
                    status = 'posted'

                    AND
                    occurred_at_utc >= ?

                    AND
                    occurred_at_utc < ?
                """,
                (
                    current_start_utc,
                    current_end_utc,
                ),
            )
            .fetchone()
        )


        inflow_minor = int(
            cash_flow[
                "inflow_minor"
            ]
            or 0
        )


        outflow_minor = int(
            cash_flow[
                "outflow_minor"
            ]
            or 0
        )



        monthly_comparison = (
            _monthly_same_elapsed(
                conn,
                coverage_start=coverage_start,
                coverage_end=coverage_end,
                timezone_name=timezone_name,
                months=4,
            )
        )


        bnpl = (
            _concept_widget_summary(
                conn,
                concept="bnpl_payment",
                start_utc=current_start_utc,
                end_utc=current_end_utc,
            )
        )


        coffee = (
            _concept_widget_summary(
                conn,
                concept="coffee",
                start_utc=current_start_utc,
                end_utc=current_end_utc,
            )
        )


        largest_transactions = (
            _largest_transactions(
                conn,
                start_utc=current_start_utc,
                end_utc=current_end_utc,
                timezone_name=timezone_name,
                limit=4,
            )
        )


        return {
            "period": {
                "start_date":
                    month_start.isoformat(),

                "end_date":
                    coverage_end.isoformat(),

                "coverage_start_date":
                    (
                        coverage_start
                        .isoformat()
                        if coverage_start
                        else None
                    ),

                "coverage_end_date":
                    coverage_end.isoformat(),

                "comparison_start_date":
                    previous_start.isoformat(),

                "comparison_end_date":
                    previous_end.isoformat(),
            },

            "balance": {
                "amount_minor":
                    (
                        int(
                            balance_minor
                        )
                        if balance_minor
                        is not None
                        else None
                    ),

                "currency":
                    currency,
            },

            "spending": {
                "amount_minor":
                    current_amount,

                "transaction_count":
                    int(
                        spending[
                            "transaction_count"
                        ]
                        or 0
                    ),

                "average_transaction_minor":
                    int(
                        spending[
                            "average_transaction_minor"
                        ]
                        or 0
                    ),

                "largest_transaction_minor":
                    int(
                        spending[
                            "largest_transaction_minor"
                        ]
                        or 0
                    ),

                "previous_same_elapsed_minor":
                    previous_amount,

                "delta_minor":
                    (
                        current_amount
                        - previous_amount
                    ),

                "daily":
                    month_daily,
            },

            "last_7_days":
                last_7_days,

            "top_merchants":
                top_merchants,

            "top_concepts":
                top_concepts,

            "cash_flow": {
                "inflow_minor":
                    inflow_minor,

                "outflow_minor":
                    outflow_minor,

                "net_minor":
                    (
                        inflow_minor
                        - outflow_minor
                    ),
            },

            "monthly_comparison":
                monthly_comparison,

            "bnpl":
                bnpl,

            "coffee":
                coffee,

            "largest_transactions":
                largest_transactions,
        }
