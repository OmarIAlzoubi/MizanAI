import sqlite3

from datetime import datetime

from datetime import datetime

from app.infrastructure.database.state import (
    get_state,
)

from datetime import datetime

from app.infrastructure.database.state import (
    get_state,
)

from app.contracts.query_spec import (
    QuerySpec,
)


class AnalyticsRepository:

    def calculate_spending(
        self,
        *,
        conn: sqlite3.Connection,
        query: QuerySpec,
        start_utc: datetime,
        end_utc: datetime,
    ) -> tuple[int, int]:

        sql = """
        SELECT
            COALESCE(
                SUM(t.amount_minor),
                0
            ) AS amount_minor,

            COUNT(t.id) AS transaction_count

        FROM transactions t

        JOIN semantic_annotations sa
            ON sa.transaction_id = t.id
            AND sa.is_active = 1

        WHERE
            t.status = 'posted'

            AND t.direction = 'debit'

            AND sa.financial_nature = 'expense'

            AND t.occurred_at_utc >= ?

            AND t.occurred_at_utc < ?
        """

        params: list = [
            start_utc.isoformat(),
            end_utc.isoformat(),
        ]

        # ---------------------------------
        # CONCEPT FILTER
        # ---------------------------------

        if query.filters.concepts:

            placeholders = ", ".join(
                "?"
                for _ in query.filters.concepts
            )

            sql += f"""
            AND EXISTS (
                SELECT 1

                FROM annotation_concepts ac

                WHERE
                    ac.annotation_id = sa.id

                    AND ac.concept IN (
                        {placeholders}
                    )
            )
            """

            params.extend(
                [
                    concept.strip().lower()
                    for concept
                    in query.filters.concepts
                ]
            )

        # ---------------------------------
        # MERCHANT FILTER
        # ---------------------------------

        if query.filters.merchants:

            placeholders = ", ".join(
                "?"
                for _ in query.filters.merchants
            )

            sql += f"""
            AND t.merchant_raw_name IN (
                {placeholders}
            )
            """

            params.extend(
                query.filters.merchants
            )

        # ---------------------------------
        # ACCOUNT FILTER
        # ---------------------------------

        if query.filters.account_ids:

            placeholders = ", ".join(
                "?"
                for _ in query.filters.account_ids
            )

            sql += f"""
            AND t.account_id IN (
                {placeholders}
            )
            """

            params.extend(
                query.filters.account_ids
            )

        # ---------------------------------
        # AMOUNT FILTERS
        # ---------------------------------

        if (
            query.filters.minimum_amount_minor
            is not None
        ):
            sql += """
            AND t.amount_minor >= ?
            """

            params.append(
                query.filters.minimum_amount_minor
            )

        if (
            query.filters.maximum_amount_minor
            is not None
        ):
            sql += """
            AND t.amount_minor <= ?
            """

            params.append(
                query.filters.maximum_amount_minor
            )

        row = conn.execute(
            sql,
            params,
        ).fetchone()

        return (
            int(
                row["amount_minor"]
                or 0
            ),
            int(
                row["transaction_count"]
                or 0
            ),
        )



    def calculate_current_balance(
        self,
        *,
        conn,
    ) -> int:

        balance_anchor_minor = get_state(
            conn,
            "balance_anchor_minor",
        )

        balance_anchor_utc = get_state(
            conn,
            "balance_anchor_utc",
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

        row = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE

                            WHEN direction = 'credit'
                            THEN amount_minor

                            WHEN direction = 'debit'
                            THEN -amount_minor

                            ELSE 0

                        END
                    ),
                    0
                ) AS net_flow_minor

            FROM transactions

            WHERE
                status = 'posted'

                AND occurred_at_utc > ?
            """,
            (
                anchor_datetime.isoformat(),
            ),
        ).fetchone()

        net_flow = int(
            row["net_flow_minor"]
            or 0
        )

        return (
            anchor_balance
            + net_flow
        )

    def calculate_current_balance(
        self,
        *,
        conn,
    ) -> int:

        balance_anchor_minor = get_state(
            conn,
            "balance_anchor_minor",
        )

        balance_anchor_utc = get_state(
            conn,
            "balance_anchor_utc",
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

        anchor_datetime = datetime.fromisoformat(
            balance_anchor_utc
        )

        row = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN direction = 'credit'
                                THEN amount_minor

                            WHEN direction = 'debit'
                                THEN -amount_minor

                            ELSE 0
                        END
                    ),
                    0
                ) AS net_flow_minor

            FROM transactions

            WHERE
                status = 'posted'
                AND occurred_at_utc > ?
            """,
            (
                anchor_datetime.isoformat(),
            ),
        ).fetchone()

        net_flow = int(
            row["net_flow_minor"]
            or 0
        )

        return (
            anchor_balance
            + net_flow
        )