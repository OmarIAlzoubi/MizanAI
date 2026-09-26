from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.recipes.repository import (
    RecipeRepository,
)

from app.application.chat_orchestrator import (
    ChatOrchestrator,
)

from app.recipes.learning_repository import (
    LearningRunFeedbackConflictError,
    LearningRunNotFoundError,
    LearningRunRepository,
)


# =========================================================
# REQUEST MODELS
# =========================================================


class ChatRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    message: str = Field(
        min_length=1,
        max_length=4000,
    )


class FeedbackRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

    run_id: str = Field(
        min_length=1,
        max_length=100,
    )

    helpful: bool


# =========================================================
# SERVICES
# =========================================================


learning_repository = (
    LearningRunRepository()
)

recipe_repository = (
    RecipeRepository()
)

chat_orchestrator = (
    ChatOrchestrator(
        learning_repository=(
            learning_repository
        )
    )
)


# =========================================================
# CHAT
# =========================================================


def handle_chat(
    request: ChatRequest,
):

    result = (
        chat_orchestrator.handle(
            request.message
        )
    )

    return {

        "response":
            result.reply,

        "message":
            result.message,

        "response_source":
            result.response_source,

        "routing": {

            "route":
                result.route,

            "confidence":
                result.route_confidence,

            "reason":
                result.route_reason,

            "agent_task":
                result.agent_task,
        },

        "plan": (
            result.plan.model_dump(
                mode="json"
            )
            if result.plan is not None
            else None
        ),

        "execution": (
            result.execution.model_dump(
                mode="json"
            )
            if result.execution is not None
            else None
        ),

        # =============================================
        # FEEDBACK
        #
        # Frontend should only show 👍 / 👎 when
        # requested == True.
        # =============================================

        "feedback": {

            "requested": (
                result.feedback_run_id
                is not None
            ),

            "run_id":
                result.feedback_run_id,
        },
    }


# =========================================================
# FEEDBACK
# =========================================================


def handle_feedback(
    request: FeedbackRequest,
):

    # =====================================================
    # GET RUN BEFORE RECORDING FEEDBACK
    #
    # We need source + recipe_id.
    # =====================================================

    run = (
        learning_repository
        .get(
            request.run_id
        )
    )

    # =====================================================
    # RECORD FEEDBACK
    #
    # Existing repository keeps this idempotent:
    #
    # same feedback again -> changed=False
    # opposite feedback   -> conflict
    # =====================================================

    result = (
        learning_repository
        .record_feedback(
            run_id=(
                request.run_id
            ),

            helpful=(
                request.helpful
            ),
        )
    )

    source = (
        run.get(
            "source"
        )
    )

    # =====================================================
    # FINANCIAL AGENT FEEDBACK
    # =====================================================

    if (
        source
        == "financial_agent"
    ):

        learning_status = (
            "eligible_for_recipe_compilation"
            if request.helpful
            else "not_eligible"
        )

    # =====================================================
    # RECIPE FEEDBACK
    # =====================================================

    elif (
        source
        == "recipe_executor"
    ):

        recipe_id = (
            run.get(
                "recipe_id"
            )
        )

        if not recipe_id:

            raise RuntimeError(
                "Recipe feedback run "
                "has no recipe_id."
            )

        # Only mutate recipe feedback counters
        # on FIRST feedback submission.
        #
        # Repeating 👍 must not keep increasing it.
        if result[
            "changed"
        ]:

            if request.helpful:

                (
                    recipe_repository
                    .record_positive_feedback(
                        recipe_id
                    )
                )

            else:

                (
                    recipe_repository
                    .record_negative_feedback(
                        recipe_id
                    )
                )

        learning_status = (
            "recipe_feedback_recorded"
        )

    # =====================================================
    # UNKNOWN SOURCE
    # =====================================================

    else:

        raise RuntimeError(
            "Unsupported learning run source: "
            f"{source}"
        )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "ok":
            True,

        "run_id":
            request.run_id,

        "source":
            source,

        "feedback": (
            "positive"
            if request.helpful
            else "negative"
        ),

        "changed":
            result[
                "changed"
            ],

        "learning_status":
            learning_status,
    }