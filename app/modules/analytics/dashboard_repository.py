import sqlite3

from datetime import datetime


class DashboardRepository:

    def spending_between(
        self,
        *,
        conn: sqlite3.Connection,
        start_utc: datetime,
        end_utc: datetime,
    ) -> int:

        row = conn.execute(
            """
            SELECT
                COALESCE(
                    SUM(t.amount_minor),
                    0
                ) AS amount_minor

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
            """,
            (
                start_utc.isoformat(),
                end_utc.isoformat(),
            ),
        ).fetchone()

        return int(
            row["amount_minor"]
            or 0
        )

    def top_categories(
        self,
        *,
        conn: sqlite3.Connection,
        start_utc: datetime,
        end_utc: datetime,
        limit: int = 5,
    ) -> list[sqlite3.Row]:

        return conn.execute(
            """
            SELECT
                ac.concept,

                SUM(
                    t.amount_minor
                ) AS amount_minor

            FROM transactions t

            JOIN semantic_annotations sa
                ON sa.transaction_id = t.id
                AND sa.is_active = 1

            JOIN annotation_concepts ac
                ON ac.annotation_id = sa.id

            WHERE
                t.status = 'posted'

                AND t.direction = 'debit'

                AND sa.financial_nature = 'expense'

                AND t.occurred_at_utc >= ?

                AND t.occurred_at_utc < ?

                AND ac.concept NOT IN (
                    'transfer',
                    'refund',
                    'debt_payment'
                )

            GROUP BY
                ac.concept

            ORDER BY
                amount_minor DESC

            LIMIT ?
            """,
            (
                start_utc.isoformat(),
                end_utc.isoformat(),
                limit,
            ),
        ).fetchall()

    def latest_transaction_time(
        self,
        *,
        conn: sqlite3.Connection,
    ) -> datetime | None:

        row = conn.execute(
            """
            SELECT MAX(
                occurred_at_utc
            ) AS latest
            FROM transactions
            """
        ).fetchone()

        value = row["latest"]

        if not value:
            return None

        return datetime.fromisoformat(
            value
        )

    def latest_balance_minor(
        self,
        *,
        conn: sqlite3.Connection,
    ) -> int | None:

        row = conn.execute(
            """
            SELECT balance_minor
            FROM transactions
            WHERE balance_minor IS NOT NULL
            ORDER BY occurred_at_utc DESC
            LIMIT 1
            """
        ).fetchone()

        if not row:
            return None

        return int(
            row["balance_minor"]
        )

    def net_flow_since(
        self,
        *,
        conn: sqlite3.Connection,
        start_utc: datetime,
    ) -> int:

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
                AND occurred_at_utc >= ?
            """,
            (
                start_utc.isoformat(),
            ),
        ).fetchone()

        return int(
            row["net_flow_minor"]
            or 0
        )


    def net_flow_after(
        self,
        *,
        conn: sqlite3.Connection,
        anchor_utc: datetime,
    ) -> int:

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
                anchor_utc.isoformat(),
            ),
        ).fetchone()

        return int(
            row["net_flow_minor"]
            or 0
        )