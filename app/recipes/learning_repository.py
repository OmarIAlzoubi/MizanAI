import json

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)


class LearningRunNotFoundError(
    LookupError
):
    pass


class LearningRunFeedbackConflictError(
    RuntimeError
):
    pass


class LearningRunRepository:

    def create_recipe_run(
        self,
        *,
        user_message: str,
        answer: str,
        execution,
        recipe_id: str,
        route_confidence: float,
        route_reason: str,
    ) -> str:

        import json

        from datetime import (
            datetime,
            timezone,
        )

        from uuid import uuid4

        run_id = str(
            uuid4()
        )

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        if hasattr(
            execution,
            "model_dump",
        ):

            execution_payload = (
                execution.model_dump(
                    mode="json"
                )
            )

        else:

            execution_payload = (
                execution
            )

        execution_json = (
            json.dumps(
                execution_payload,
                ensure_ascii=False,
            )
        )

        with self.database.session() as conn:

            conn.execute(
                """
                INSERT INTO analysis_learning_runs (
                    id,
                    source,
                    user_message,
                    agent_task,
                    route_confidence,
                    route_reason,
                    answer,
                    execution_json,
                    feedback,
                    recipe_id,
                    created_at_utc,
                    feedback_at_utc
                )
                VALUES (
                    ?,
                    'recipe_executor',
                    ?,
                    NULL,
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    ?,
                    ?,
                    NULL
                )
                """,
                (
                    run_id,
                    user_message,
                    route_confidence,
                    route_reason,
                    answer,
                    execution_json,
                    recipe_id,
                    now,
                ),
            )

        return run_id

    def __init__(
        self,
        database: Database | None = None,
    ):

        self.database = (
            database
            or get_default_database()
        )

    # =====================================================
    # CREATE AGENT RUN
    # =====================================================

    def create_agent_run(
        self,
        *,
        user_message: str,
        agent_task: str,
        route_confidence: float | None,
        route_reason: str | None,
        answer: str,
        execution: dict,
    ) -> str:

        user_message = (
            user_message.strip()
        )

        agent_task = (
            agent_task.strip()
        )

        answer = (
            answer.strip()
        )

        if not user_message:
            raise ValueError(
                "user_message cannot be empty."
            )

        if not agent_task:
            raise ValueError(
                "agent_task cannot be empty."
            )

        if not answer:
            raise ValueError(
                "answer cannot be empty."
            )

        run_id = str(
            uuid4()
        )

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        execution_json = json.dumps(
            execution,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        with self.database.session() as conn:

            conn.execute(
                """
                INSERT INTO analysis_learning_runs (
                    id,
                    source,
                    user_message,
                    agent_task,
                    route_confidence,
                    route_reason,
                    answer,
                    execution_json,
                    feedback,
                    recipe_id,
                    created_at_utc,
                    feedback_at_utc
                )
                VALUES (
                    ?,
                    'financial_agent',
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    NULL,
                    ?,
                    NULL
                )
                """,
                (
                    run_id,
                    user_message,
                    agent_task,
                    route_confidence,
                    route_reason,
                    answer,
                    execution_json,
                    now,
                ),
            )

        return run_id

    # =====================================================
    # GET
    # =====================================================

    def get(
        self,
        run_id: str,
    ) -> dict:

        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT
                    id,
                    source,
                    user_message,
                    agent_task,
                    route_confidence,
                    route_reason,
                    answer,
                    execution_json,
                    feedback,
                    recipe_id,
                    created_at_utc,
                    feedback_at_utc
                FROM analysis_learning_runs
                WHERE id = ?
                """,
                (
                    run_id,
                ),
            ).fetchone()

        if row is None:

            raise LearningRunNotFoundError(
                f"Learning run not found: "
                f"{run_id}"
            )

        return {
            "id":
                row["id"],

            "source":
                row["source"],

            "user_message":
                row["user_message"],

            "agent_task":
                row["agent_task"],

            "route_confidence":
                row["route_confidence"],

            "route_reason":
                row["route_reason"],

            "answer":
                row["answer"],

            "execution":
                json.loads(
                    row["execution_json"]
                ),

            "feedback":
                row["feedback"],

            "recipe_id":
                row["recipe_id"],

            "created_at_utc":
                row["created_at_utc"],

            "feedback_at_utc":
                row["feedback_at_utc"],
        }

    # =====================================================
    # FEEDBACK
    # =====================================================

    def record_feedback(
        self,
        *,
        run_id: str,
        helpful: bool,
    ) -> dict:

        desired_feedback = (
            "positive"
            if helpful
            else "negative"
        )

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT
                    id,
                    feedback
                FROM analysis_learning_runs
                WHERE id = ?
                """,
                (
                    run_id,
                ),
            ).fetchone()

            if row is None:

                raise LearningRunNotFoundError(
                    f"Learning run not found: "
                    f"{run_id}"
                )

            current_feedback = (
                row["feedback"]
            )

            # ---------------------------------------------
            # Idempotent retry.
            #
            # If frontend accidentally submits the same
            # feedback twice, do not fail.
            # ---------------------------------------------

            if (
                current_feedback
                == desired_feedback
            ):

                return {
                    "run_id":
                        run_id,

                    "feedback":
                        desired_feedback,

                    "changed":
                        False,
                }

            # ---------------------------------------------
            # For V1 feedback is final once submitted.
            # This avoids compiling one run as both
            # positive and negative later.
            # ---------------------------------------------

            if current_feedback is not None:

                raise (
                    LearningRunFeedbackConflictError(
                        "Feedback has already "
                        "been submitted for "
                        "this learning run."
                    )
                )

            conn.execute(
                """
                UPDATE analysis_learning_runs
                SET
                    feedback = ?,
                    feedback_at_utc = ?
                WHERE id = ?
                """,
                (
                    desired_feedback,
                    now,
                    run_id,
                ),
            )

        return {
            "run_id":
                run_id,

            "feedback":
                desired_feedback,

            "changed":
                True,
        }

    # =====================================================
    # ATTACH RECIPE
    #
    # We will use this later when Recipe Compiler exists.
    # =====================================================

    def attach_recipe(
        self,
        *,
        run_id: str,
        recipe_id: str,
    ) -> None:

        with self.database.session() as conn:

            cursor = conn.execute(
                """
                UPDATE analysis_learning_runs
                SET recipe_id = ?
                WHERE id = ?
                """,
                (
                    recipe_id,
                    run_id,
                ),
            )

            if cursor.rowcount == 0:

                raise LearningRunNotFoundError(
                    f"Learning run not found: "
                    f"{run_id}"
                )