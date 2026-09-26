import sqlite3


TRANSACTIONS_VIEW = (
    "v_financial_transactions"
)

CONCEPTS_VIEW = (
    "v_financial_concepts"
)

SNAPSHOT_VIEW = (
    "v_financial_snapshot"
)


def ensure_financial_views(
    conn: sqlite3.Connection,
) -> None:

    # =====================================================
    # TRANSACTION-LEVEL ANALYTICAL VIEW
    #
    # One row = one transaction.
    #
    # This is the primary view for:
    #
    # - totals
    # - periods
    # - merchants
    # - transaction inspection
    # - financial nature
    # =====================================================

    conn.execute(
        f"""
        CREATE VIEW IF NOT EXISTS
        {TRANSACTIONS_VIEW}
        AS

        SELECT

            t.id
                AS transaction_id,

            t.amount_minor
                AS amount_minor,

            t.currency
                AS currency,

            t.direction
                AS direction,

            CASE

                WHEN t.direction = 'credit'
                    THEN t.amount_minor

                WHEN t.direction = 'debit'
                    THEN -t.amount_minor

                ELSE 0

            END
                AS signed_amount_minor,

            t.occurred_at_utc
                AS occurred_at_utc,

            t.posted_at_utc
                AS posted_at_utc,

            t.status
                AS status,

            t.merchant_raw_name
                AS merchant,

            t.raw_description
                AS description,

            t.source
                AS source,

            sa.financial_nature
                AS financial_nature,

            (
                SELECT
                    GROUP_CONCAT(
                        ordered_concepts.concept,
                        '|'
                    )

                FROM (
                    SELECT
                        ac.concept

                    FROM annotation_concepts ac

                    WHERE
                        ac.annotation_id = sa.id

                    ORDER BY
                        ac.concept
                )
                AS ordered_concepts

            )
                AS concepts

        FROM transactions t

        LEFT JOIN semantic_annotations sa

            ON sa.id = (

                SELECT
                    sa2.id

                FROM semantic_annotations sa2

                WHERE
                    sa2.transaction_id = t.id

                    AND
                    sa2.is_active = 1

                ORDER BY
                    sa2.version DESC,
                    sa2.created_at_utc DESC

                LIMIT 1
            )
        """
    )

    # =====================================================
    # CONCEPT ANALYTICAL VIEW
    #
    # One row = transaction + one concept.
    #
    # Useful for:
    #
    # GROUP BY concept
    # ranking concepts
    # comparing concept behavior
    #
    # IMPORTANT:
    # concepts are multi-dimensional tags.
    # A transaction may appear more than once here.
    # =====================================================

    conn.execute(
        f"""
        CREATE VIEW IF NOT EXISTS
        {CONCEPTS_VIEW}
        AS

        SELECT

            t.id
                AS transaction_id,

            ac.concept
                AS concept,

            t.amount_minor
                AS amount_minor,

            t.currency
                AS currency,

            t.direction
                AS direction,

            t.occurred_at_utc
                AS occurred_at_utc,

            t.status
                AS status,

            t.merchant_raw_name
                AS merchant,

            t.raw_description
                AS description,

            sa.financial_nature
                AS financial_nature

        FROM transactions t

        JOIN semantic_annotations sa

            ON sa.id = (

                SELECT
                    sa2.id

                FROM semantic_annotations sa2

                WHERE
                    sa2.transaction_id = t.id

                    AND
                    sa2.is_active = 1

                ORDER BY
                    sa2.version DESC,
                    sa2.created_at_utc DESC

                LIMIT 1
            )

        JOIN annotation_concepts ac

            ON ac.annotation_id = sa.id
        """
    )

    # =====================================================
    # CURRENT FINANCIAL SNAPSHOT
    #
    # Exposes current verified balance without giving
    # the agent direct access to app_state.
    # =====================================================

    conn.execute(
        f"""
        CREATE VIEW IF NOT EXISTS
        {SNAPSHOT_VIEW}
        AS

        WITH anchor AS (

            SELECT

                CAST(
                    MAX(
                        CASE
                            WHEN key =
                                'balance_anchor_minor'
                            THEN value
                        END
                    )
                    AS INTEGER
                )
                    AS anchor_balance_minor,

                MAX(
                    CASE
                        WHEN key =
                            'balance_anchor_utc'
                        THEN value
                    END
                )
                    AS anchor_utc

            FROM app_state
        ),

        flow AS (

            SELECT

                COALESCE(
                    SUM(
                        CASE

                            WHEN t.direction = 'credit'
                                THEN t.amount_minor

                            WHEN t.direction = 'debit'
                                THEN -t.amount_minor

                            ELSE 0

                        END
                    ),
                    0
                )
                    AS net_flow_minor

            FROM transactions t

            CROSS JOIN anchor a

            WHERE
                t.status = 'posted'

                AND
                a.anchor_utc IS NOT NULL

                AND
                t.occurred_at_utc
                    > a.anchor_utc
        )

        SELECT

            CASE

                WHEN
                    a.anchor_balance_minor
                    IS NULL

                THEN NULL

                ELSE
                    a.anchor_balance_minor
                    + f.net_flow_minor

            END
                AS current_balance_minor,

            'SAR'
                AS currency,

            a.anchor_utc
                AS balance_anchor_utc,

            (
                SELECT
                    MAX(
                        occurred_at_utc
                    )

                FROM transactions

                WHERE
                    status = 'posted'
            )
                AS latest_transaction_utc

        FROM anchor a

        CROSS JOIN flow f
        """
    )