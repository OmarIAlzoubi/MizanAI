from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.infrastructure.database.connection import (
    Database,
)


def seed_demo_data(
    *,
    database: Database,
    timezone_name: str = (
        "Asia/Riyadh"
    ),
) -> int:

    tz = ZoneInfo(
        timezone_name
    )

    now_local = datetime.now(
        tz
    )

    rows = [
        (-34, "credit", "12000.00", "Salary", "income", ("salary",)),
        (-31, "debit", "2500.00", "Rent", "expense", ("housing",)),
        (-28, "debit", "42.00", "Uber", "expense", ("transport",)),
        (-25, "debit", "28.00", "Starbucks", "expense", ("coffee",)),
        (-23, "debit", "219.00", "Jarir", "expense", ("shopping",)),
        (-20, "debit", "230.00", "STC", "expense", ("telecom",)),
        (-17, "debit", "61.50", "HungerStation", "expense", ("food",)),
        (-14, "debit", "19.00", "Half Million", "expense", ("coffee",)),
        (-11, "debit", "76.00", "Amazon", "expense", ("shopping",)),
        (-9, "debit", "35.00", "Uber", "expense", ("transport",)),
        (-7, "debit", "47.00", "AlBaik", "expense", ("food",)),
        (-5, "debit", "22.00", "Coffee Address", "expense", ("coffee",)),
        (-3, "debit", "100.00", "Ehsan", "expense", ("charity",)),
        (-2, "debit", "89.00", "Panda", "expense", ("groceries",)),
        (-1, "debit", "18.00", "Starbucks", "expense", ("coffee",)),
    ]

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    with database.session() as conn:

        existing = (
            conn.execute(
                "SELECT COUNT(*) FROM transactions"
            )
            .fetchone()[0]
        )

        if existing:
            raise RuntimeError(
                "Demo seeding requires "
                "an empty transaction ledger."
            )

        count = 0

        for (
            day_offset,
            direction,
            amount_text,
            merchant,
            nature,
            concepts,
        ) in rows:

            occurred_local = (
                now_local
                + timedelta(
                    days=day_offset
                )
            ).replace(
                hour=12,
                minute=0,
                second=0,
                microsecond=0,
            )

            occurred_utc = (
                occurred_local
                .astimezone(
                    timezone.utc
                )
                .isoformat()
            )

            amount_minor = int(
                Decimal(
                    amount_text
                )
                * 100
            )

            tx_id = str(
                uuid4()
            )

            annotation_id = str(
                uuid4()
            )

            conn.execute(
                """
                INSERT INTO transactions (
                    id,
                    account_id,
                    amount_minor,
                    currency,
                    direction,
                    occurred_at_utc,
                    posted_at_utc,
                    status,
                    merchant_raw_name,
                    raw_description,
                    source,
                    created_at_utc
                )
                VALUES (
                    ?,
                    'primary',
                    ?,
                    'SAR',
                    ?,
                    ?,
                    ?,
                    'posted',
                    ?,
                    ?,
                    'demo',
                    ?
                )
                """,
                (
                    tx_id,
                    amount_minor,
                    direction,
                    occurred_utc,
                    occurred_utc,
                    merchant,
                    (
                        "Synthetic demo "
                        f"transaction: {merchant}"
                    ),
                    created_at,
                ),
            )

            conn.execute(
                """
                INSERT INTO
                semantic_annotations (
                    id,
                    transaction_id,
                    financial_nature,
                    source,
                    version,
                    is_active,
                    created_at_utc
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    'demo_seed',
                    1,
                    1,
                    ?
                )
                """,
                (
                    annotation_id,
                    tx_id,
                    nature,
                    created_at,
                ),
            )

            for concept in concepts:

                conn.execute(
                    """
                    INSERT INTO
                    annotation_concepts (
                        annotation_id,
                        concept
                    )
                    VALUES (?, ?)
                    """,
                    (
                        annotation_id,
                        concept,
                    ),
                )

            count += 1

        # Demo transactions are historical.
        # This is the verified current-balance
        # anchor after those transactions.
        _set_state(
            conn,
            key="balance_anchor_minor",
            value=str(
                845000
            ),
        )

        _set_state(
            conn,
            key="balance_anchor_utc",
            value=(
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        )

        _set_state(
            conn,
            key="bootstrap_source",
            value="demo",
        )

    return count


def set_fresh_balance(
    *,
    database: Database,
    balance_minor: int,
) -> None:

    with database.session() as conn:

        _set_state(
            conn,
            key="balance_anchor_minor",
            value=str(
                balance_minor
            ),
        )

        _set_state(
            conn,
            key="balance_anchor_utc",
            value=(
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
        )

        _set_state(
            conn,
            key="bootstrap_source",
            value="fresh",
        )


def _set_state(
    conn,
    *,
    key: str,
    value: str,
) -> None:

    conn.execute(
        """
        INSERT INTO app_state (
            key,
            value,
            updated_at_utc
        )
        VALUES (
            ?,
            ?,
            datetime('now')
        )
        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value,
            updated_at_utc =
                excluded.updated_at_utc
        """,
        (
            key,
            value,
        ),
    )
