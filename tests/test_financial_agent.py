from app.agent.financial_agent import (
    FinancialAgent,
)

from app.infrastructure.database.schema import (
    initialize_database,
)


def main():

    initialize_database()

    agent = FinancialAgent()

    result = agent.run(
        user_message=(
            "ليش صرفي مرتفع هذا الشهر؟"
        ),

        task=(
            "Investigate why the user's spending "
            "is elevated this month, verify whether "
            "it is actually unusually high, and "
            "identify the strongest contributing "
            "factors or patterns."
        ),
    )

    print(
        "\n"
        "=============================="
    )

    print(
        "FINAL ANSWER"
    )

    print(
        "=============================="
    )

    print(
        result.answer
    )

    print(
        "\n"
        "STATUS:"
    )

    print(
        result.status
    )

    print(
        "\n"
        "STEPS:"
    )

    print(
        len(result.steps)
    )


if __name__ == "__main__":
    main()