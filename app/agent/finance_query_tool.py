from __future__ import annotations

import sqlite3

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.agent.sql_guard import (
    FinancialSQLGuard,
)

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)


class FinanceQueryTimeoutError(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class FinanceQueryResult:

    columns: list[str]

    rows: list[
        dict[str, Any]
    ]

    row_count: int

    truncated: bool


class FinanceQueryTool:

    DEFAULT_MAX_ROWS = 100

    DEFAULT_TIMEOUT_SECONDS = 2.0

    def __init__(
        self,
        database: Database | None = None,
        max_rows: int = DEFAULT_MAX_ROWS,
        timeout_seconds: float = (
            DEFAULT_TIMEOUT_SECONDS
        ),
    ):

        self.database = (
            database
            or get_default_database()
        )

        self.max_rows = max_rows

        self.timeout_seconds = (
            timeout_seconds
        )

    # =====================================================
    # EXECUTE
    # =====================================================

    def execute(
        self,
        sql: str,
    ) -> FinanceQueryResult:

        safe_sql = (
            FinancialSQLGuard
            .validate(
                sql
            )
        )

        with self.database.session() as conn:

            return (
                self._execute_read_only(
                    conn=conn,
                    sql=safe_sql,
                )
            )

    # =====================================================
    # INTERNAL
    # =====================================================

    def _execute_read_only(
        self,
        *,
        conn: sqlite3.Connection,
        sql: str,
    ) -> FinanceQueryResult:

        deadline = (
            perf_counter()
            + self.timeout_seconds
        )

        timed_out = False

        def progress_handler():

            nonlocal timed_out

            if perf_counter() > deadline:

                timed_out = True

                return 1

            return 0

        # SQLite checks this callback
        # periodically while executing.
        conn.set_progress_handler(
            progress_handler,
            5000,
        )

        conn.execute(
            "PRAGMA query_only = ON"
        )

        try:

            cursor = conn.execute(
                sql
            )

            columns = [

                item[0]

                for item
                in cursor.description
            ]

            raw_rows = (
                cursor.fetchmany(
                    self.max_rows + 1
                )
            )

            truncated = (
                len(raw_rows)
                > self.max_rows
            )

            raw_rows = raw_rows[
                :self.max_rows
            ]

            rows = [
                dict(row)
                for row
                in raw_rows
            ]

            return FinanceQueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                truncated=truncated,
            )

        except sqlite3.OperationalError as exc:

            if timed_out:

                raise FinanceQueryTimeoutError(
                    "Financial query exceeded "
                    "the execution time limit."
                ) from exc

            raise

        finally:

            conn.set_progress_handler(
                None,
                0,
            )

            conn.execute(
                "PRAGMA query_only = OFF"
            )