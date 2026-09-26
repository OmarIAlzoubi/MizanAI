from time import perf_counter

from app.ai.understanding import (
    UnderstandingService,
)
from app.application.action_executor import (
    ActionExecutor,
)
from app.core.config import BASE_DIR
from app.infrastructure.database.connection import (
    Database,
)
from app.infrastructure.database.schema import (
    initialize_database,
)
from app.modules.analytics.service import (
    AnalyticsService,
)
from app.modules.transactions.service import (
    TransactionService,
)


def main():

    # =================================
    # TEST DATABASE
    # =================================

    db_path = (
        BASE_DIR
        / "data"
        / "mizan_test.db"
    )

    if db_path.exists():
        db_path.unlink()

    database = Database(
        db_path
    )

    initialize_database(
        database
    )

    # =================================
    # SERVICES
    # =================================

    understanding = (
        UnderstandingService()
    )

    transaction_service = (
        TransactionService(
            database=database
        )
    )

    analytics_service = (
        AnalyticsService(
            database=database
        )
    )

    executor = ActionExecutor(
        transaction_service=(
            transaction_service
        ),
        analytics_service=(
            analytics_service
        ),
    )

    # =================================
    # STEP 1 — WRITE
    # =================================

    write_message = (
        "دفعت 300 ريال في إحسان أمس"
    )

    print("\n====================")
    print("WRITE")
    print("====================")

    print("\nUSER")
    print(write_message)

    # ---------------------------------
    # UNDERSTANDING
    # ---------------------------------

    write_total_start = perf_counter()

    write_understanding = (
        understanding.understand(
            message=write_message
        )
    )

    write_understanding_total_ms = (
        perf_counter()
        - write_total_start
    ) * 1000

    print("\nACTION PLAN")
    print(
        write_understanding
        .data
        .model_dump_json(
            indent=2
        )
    )

    print(
        "\nWRITE LLM LATENCY:",
        f"{write_understanding.latency_ms:.0f} ms"
    )

    print(
        "WRITE UNDERSTANDING TOTAL:",
        f"{write_understanding_total_ms:.0f} ms"
    )

    # ---------------------------------
    # EXECUTION
    # ---------------------------------

    write_execution_start = (
        perf_counter()
    )

    write_result = executor.execute(
        plan=write_understanding.data,
        user_message=write_message,
    )

    write_execution_ms = (
        perf_counter()
        - write_execution_start
    ) * 1000

    print("\nEXECUTION")
    print(
        write_result.model_dump_json(
            indent=2
        )
    )

    print(
        "\nWRITE EXECUTION LATENCY:",
        f"{write_execution_ms:.2f} ms"
    )

    # =================================
    # STEP 2 — READ
    # =================================

    read_message = (
        "كم تبرعت هذا الشهر؟"
    )

    print("\n====================")
    print("READ")
    print("====================")

    print("\nUSER")
    print(read_message)

    # ---------------------------------
    # UNDERSTANDING
    # ---------------------------------

    read_total_start = (
        perf_counter()
    )

    read_understanding = (
        understanding.understand(
            message=read_message
        )
    )

    read_understanding_total_ms = (
        perf_counter()
        - read_total_start
    ) * 1000

    print("\nACTION PLAN")
    print(
        read_understanding
        .data
        .model_dump_json(
            indent=2
        )
    )

    print(
        "\nREAD LLM LATENCY:",
        f"{read_understanding.latency_ms:.0f} ms"
    )

    print(
        "READ UNDERSTANDING TOTAL:",
        f"{read_understanding_total_ms:.0f} ms"
    )

    # ---------------------------------
    # EXECUTION
    # ---------------------------------

    read_execution_start = (
        perf_counter()
    )

    read_result = executor.execute(
        plan=read_understanding.data,
        user_message=read_message,
    )

    read_execution_ms = (
        perf_counter()
        - read_execution_start
    ) * 1000

    print("\nEXECUTION")
    print(
        read_result.model_dump_json(
            indent=2
        )
    )

    print(
        "\nREAD EXECUTION LATENCY:",
        f"{read_execution_ms:.2f} ms"
    )

    # =================================
    # VERIFY RESULT
    # =================================

    action_result = (
        read_result.actions[0]
    )

    amount_minor = (
        action_result
        .data["amount_minor"]
    )

    print("\n====================")
    print("FINAL")
    print("====================")

    print(
        f"{amount_minor / 100:.2f} SAR"
    )

    assert amount_minor == 30000

    print(
        "\nPASS: Expected spending "
        "result = 300 SAR"
    )

    # =================================
    # LATENCY SUMMARY
    # =================================

    print("\n====================")
    print("LATENCY SUMMARY")
    print("====================")

    print(
        "WRITE LLM:",
        f"{write_understanding.latency_ms:.0f} ms"
    )

    print(
        "WRITE UNDERSTANDING TOTAL:",
        f"{write_understanding_total_ms:.0f} ms"
    )

    print(
        "WRITE EXECUTION:",
        f"{write_execution_ms:.2f} ms"
    )

    print()

    print(
        "READ LLM:",
        f"{read_understanding.latency_ms:.0f} ms"
    )

    print(
        "READ UNDERSTANDING TOTAL:",
        f"{read_understanding_total_ms:.0f} ms"
    )

    print(
        "READ EXECUTION:",
        f"{read_execution_ms:.2f} ms"
    )


if __name__ == "__main__":
    main()