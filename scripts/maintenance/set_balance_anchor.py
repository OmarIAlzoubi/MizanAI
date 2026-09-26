import sys

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from app.infrastructure.database.connection import (
    get_default_database,
)

from app.infrastructure.database.schema import (
    initialize_database,
)

from app.infrastructure.database.state import (
    set_state,
)


def sar_to_minor(
    value: str,
) -> int:

    amount = Decimal(
        value
    )

    minor = (
        amount
        * Decimal("100")
    ).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )

    return int(
        minor
    )


def main():

    if len(sys.argv) != 2:

        print(
            "Usage:"
        )

        print(
            "python set_balance_anchor.py 5451.51"
        )

        raise SystemExit(1)

    balance_minor = (
        sar_to_minor(
            sys.argv[1]
        )
    )

    database = (
        get_default_database()
    )

    initialize_database(
        database
    )

    with database.session() as conn:

        row = conn.execute(
            """
            SELECT
                MAX(
                    occurred_at_utc
                ) AS latest
            FROM transactions
            """
        ).fetchone()

        latest_utc = (
            row["latest"]
        )

        if not latest_utc:

            raise RuntimeError(
                "No transactions found."
            )

        set_state(
            conn,
            "balance_anchor_minor",
            balance_minor,
        )

        set_state(
            conn,
            "balance_anchor_utc",
            latest_utc,
        )

    print()
    print(
        "Balance anchor saved."
    )

    print(
        "Balance minor:",
        balance_minor,
    )

    print(
        "Anchor UTC:",
        latest_utc,
    )


if __name__ == "__main__":
    main()