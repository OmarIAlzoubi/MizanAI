import sys

from datetime import date

from app.infrastructure.database.connection import (
    get_default_database,
)

from app.infrastructure.database.state import (
    set_transactions_coverage_through_local_date,
)


def main():

    if len(sys.argv) != 2:

        raise SystemExit(
            "Usage: "
            "python set_data_coverage.py YYYY-MM-DD"
        )

    raw_date = (
        sys.argv[1]
        .strip()
    )

    try:

        coverage_date = (
            date.fromisoformat(
                raw_date
            )
        )

    except ValueError as exc:

        raise SystemExit(
            "Invalid date. "
            "Use YYYY-MM-DD."
        ) from exc

    database = (
        get_default_database()
    )

    with database.session() as conn:

        set_transactions_coverage_through_local_date(
            conn,
            coverage_date,
        )

    print(
        "Transaction coverage watermark set to:",
        coverage_date.isoformat(),
    )


if __name__ == "__main__":

    main()