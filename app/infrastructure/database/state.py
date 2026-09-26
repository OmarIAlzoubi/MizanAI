from datetime import (
    datetime,
    timezone,
)

import sqlite3


def get_state(
    conn: sqlite3.Connection,
    key: str,
) -> str | None:

    row = conn.execute(
        """
        SELECT value
        FROM app_state
        WHERE key = ?
        """,
        (
            key,
        ),
    ).fetchone()

    if not row:
        return None

    return row["value"]


def set_state(
    conn: sqlite3.Connection,
    key: str,
    value: str | int | float,
) -> None:

    conn.execute(
        """
        INSERT INTO app_state (
            key,
            value,
            updated_at_utc
        )
        VALUES (?, ?, ?)

        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value,
            updated_at_utc = excluded.updated_at_utc
        """,
        (
            key,
            str(value),
            datetime.now(
                timezone.utc
            ).isoformat(),
        ),
    )