from app.infrastructure.database.schema import (
    initialize_database,
)

from app.agent.finance_query_tool import (
    FinanceQueryTool,
)


def main():

    initialize_database()

    tool = FinanceQueryTool()

    # =============================================
    # TEST 1
    # TOP CONCEPTS
    # =============================================

    result = tool.execute(
        """
        SELECT
            concept,
            COUNT(DISTINCT transaction_id)
                AS transaction_count,
            SUM(amount_minor)
                AS total_minor

        FROM v_financial_concepts

        WHERE
            status = 'posted'
            AND direction = 'debit'
            AND financial_nature = 'expense'

        GROUP BY
            concept

        ORDER BY
            total_minor DESC

        LIMIT 10
        """
    )

    print(
        "\nTOP CONCEPTS"
    )

    for row in result.rows:
        print(row)

    # =============================================
    # TEST 2
    # CURRENT BALANCE
    # =============================================

    balance = tool.execute(
        """
        SELECT
            current_balance_minor,
            currency,
            balance_anchor_utc,
            latest_transaction_utc

        FROM v_financial_snapshot
        """
    )

    print(
        "\nCURRENT SNAPSHOT"
    )

    for row in balance.rows:
        print(row)

    # =============================================
    # TEST 3
    # SHOULD FAIL
    # =============================================

    try:

        tool.execute(
            """
            SELECT *
            FROM transactions
            """
        )

    except Exception as exc:

        print(
            "\nBLOCKED AS EXPECTED"
        )

        print(
            type(exc).__name__,
            ":",
            exc,
        )


if __name__ == "__main__":
    main()