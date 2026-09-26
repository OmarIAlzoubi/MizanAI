from pathlib import Path

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
from app.modules.transactions.service import (
    TransactionService,
)


def main():

    # ---------------------------------
    # CLEAN TEST DATABASE
    # ---------------------------------

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

    # ---------------------------------
    # SERVICES
    # ---------------------------------

    understanding = (
        UnderstandingService()
    )

    transaction_service = (
        TransactionService(
            database=database
        )
    )

    executor = ActionExecutor(
        transaction_service=(
            transaction_service
        )
    )

    # ---------------------------------
    # USER MESSAGE
    # ---------------------------------

    message = (
        "دفعت 300 ريال في إحسان أمس"
    )

    print("\nUSER")
    print(message)

    # ---------------------------------
    # UNDERSTANDING
    # ---------------------------------

    llm_result = (
        understanding.understand(
            message=message
        )
    )

    print("\nACTION PLAN")
    print(
        llm_result.data
        .model_dump_json(
            indent=2
        )
    )

    # ---------------------------------
    # EXECUTION
    # ---------------------------------

    execution = executor.execute(
        plan=llm_result.data,
        user_message=message,
    )

    print("\nEXECUTION RESULT")
    print(
        execution.model_dump_json(
            indent=2
        )
    )

    # ---------------------------------
    # VERIFY DATABASE
    # ---------------------------------

    with database.session() as conn:

        transaction = conn.execute(
            """
            SELECT *
            FROM transactions
            LIMIT 1
            """
        ).fetchone()

        annotation = conn.execute(
            """
            SELECT *
            FROM semantic_annotations
            LIMIT 1
            """
        ).fetchone()

        concepts = conn.execute(
            """
            SELECT concept
            FROM annotation_concepts
            """
        ).fetchall()

    print("\nDATABASE TRANSACTION")
    print(
        dict(transaction)
    )

    print("\nDATABASE ANNOTATION")
    print(
        dict(annotation)
    )

    print("\nDATABASE CONCEPTS")
    print(
        [
            row["concept"]
            for row in concepts
        ]
    )


if __name__ == "__main__":
    main()