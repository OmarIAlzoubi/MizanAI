import sqlite3

from app.modules.transactions.models import (
    SemanticAnnotationRecord,
    TransactionRecord,
)


class TransactionRepository:

    def list_recent(
        self,
        conn: sqlite3.Connection,
        *,
        limit: int = 50,
    ) -> list[sqlite3.Row]:

        return conn.execute(
            """
            SELECT
                t.id,
                t.amount_minor,
                t.currency,
                t.direction,
                t.occurred_at_utc,
                t.merchant_raw_name,
                t.raw_description,

                sa.financial_nature,

                GROUP_CONCAT(
                    DISTINCT ac.concept
                ) AS concepts

            FROM transactions t

            LEFT JOIN semantic_annotations sa
                ON sa.transaction_id = t.id
                AND sa.is_active = 1

            LEFT JOIN annotation_concepts ac
                ON ac.annotation_id = sa.id

            WHERE
                t.status = 'posted'

            GROUP BY
                t.id,
                t.amount_minor,
                t.currency,
                t.direction,
                t.occurred_at_utc,
                t.merchant_raw_name,
                t.raw_description,
                sa.financial_nature

            ORDER BY
                t.occurred_at_utc DESC,
                t.created_at_utc DESC

            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def create(
        self,
        conn: sqlite3.Connection,
        transaction: TransactionRecord,
    ) -> None:

        conn.execute(
            """
            INSERT INTO transactions (
                id,
                account_id,
                amount_minor,
                currency,
                direction,
                occurred_at_utc,
                status,
                merchant_raw_name,
                raw_description,
                source,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                transaction.id,
                transaction.account_id,
                transaction.amount_minor,
                transaction.currency,
                transaction.direction.value,
                transaction.occurred_at_utc.isoformat(),
                transaction.status,
                transaction.merchant_raw_name,
                transaction.raw_description,
                transaction.source,
                transaction.created_at_utc.isoformat(),
            ),
        )

    def get_by_id(
        self,
        conn: sqlite3.Connection,
        transaction_id: str,
    ) -> sqlite3.Row | None:

        return conn.execute(
            """
            SELECT *
            FROM transactions
            WHERE id = ?
            """,
            (transaction_id,),
        ).fetchone()

    def get_execution_data(
        self,
        conn: sqlite3.Connection,
        transaction_id: str,
    ) -> sqlite3.Row | None:

        return conn.execute(
            """
            SELECT
                t.id
                    AS transaction_id,

                t.amount_minor
                    AS amount_minor,

                t.currency
                    AS currency,

                t.direction
                    AS direction,

                t.occurred_at_utc
                    AS occurred_at_utc,

                t.merchant_raw_name
                    AS merchant,

                sa.financial_nature
                    AS financial_nature,

                GROUP_CONCAT(
                    ac.concept,
                    '|'
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

            LEFT JOIN annotation_concepts ac
                ON ac.annotation_id = sa.id

            WHERE t.id = ?

            GROUP BY
                t.id,
                t.amount_minor,
                t.currency,
                t.direction,
                t.occurred_at_utc,
                t.merchant_raw_name,
                sa.financial_nature

            LIMIT 1
            """,
            (
                transaction_id,
            ),
        ).fetchone()

    
class TransactionIdempotencyRepository:

    def claim(
        self,
        conn: sqlite3.Connection,
        *,
        idempotency_key: str,
        created_at_utc: str,
    ) -> tuple[
        bool,
        str | None,
    ]:

        cursor = conn.execute(
            """
            INSERT INTO transaction_idempotency (
                idempotency_key,
                transaction_id,
                created_at_utc
            )
            VALUES (?, NULL, ?)

            ON CONFLICT(idempotency_key)
            DO NOTHING
            """,
            (
                idempotency_key,
                created_at_utc,
            ),
        )


        if cursor.rowcount == 1:

            return (
                True,
                None,
            )


        row = conn.execute(
            """
            SELECT
                transaction_id

            FROM transaction_idempotency

            WHERE idempotency_key = ?

            LIMIT 1
            """,
            (
                idempotency_key,
            ),
        ).fetchone()


        if row is None:

            raise RuntimeError(
                "Idempotency key could not "
                "be resolved."
            )


        transaction_id = (
            row[
                "transaction_id"
            ]
        )


        if not transaction_id:

            raise RuntimeError(
                "Idempotency key exists "
                "without transaction_id."
            )


        return (
            False,
            transaction_id,
        )


    def bind_transaction(
        self,
        conn: sqlite3.Connection,
        *,
        idempotency_key: str,
        transaction_id: str,
    ) -> None:

        cursor = conn.execute(
            """
            UPDATE transaction_idempotency

            SET transaction_id = ?

            WHERE idempotency_key = ?
              AND transaction_id IS NULL
            """,
            (
                transaction_id,
                idempotency_key,
            ),
        )


        if cursor.rowcount != 1:

            raise RuntimeError(
                "Could not bind transaction "
                "to idempotency key."
            )

        
class SemanticAnnotationRepository:

    def create(
        self,
        conn: sqlite3.Connection,
        annotation: SemanticAnnotationRecord,
    ) -> None:

        conn.execute(
            """
            INSERT INTO semantic_annotations (
                id,
                transaction_id,
                financial_nature,
                source,
                version,
                is_active,
                created_at_utc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                annotation.id,
                annotation.transaction_id,
                annotation.financial_nature.value,
                annotation.source,
                annotation.version,
                int(
                    annotation.is_active
                ),
                annotation.created_at_utc.isoformat(),
            ),
        )

        if annotation.concepts:
            conn.executemany(
                """
                INSERT INTO annotation_concepts (
                    annotation_id,
                    concept
                )
                VALUES (?, ?)
                """,
                [
                    (
                        annotation.id,
                        concept,
                    )
                    for concept
                    in annotation.concepts
                ],
            )