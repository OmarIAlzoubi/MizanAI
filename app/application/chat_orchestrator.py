from dataclasses import (
    dataclass,
    replace,
)

from app.ai.conversation_reasoner import (
    ConversationReasoner,
)

from app.application.conversation_memory import (
    ConversationMemory,
)

from app.application.friendly_conversation import (
    FriendlyConversationService,
)

from app.ai.recipe_result_composer import (
    RecipeResultComposer,
)

from app.contracts.recipe_execution import (
    RecipeExecutionResult,
)

from app.recipes.executor import (
    RecipeExecutor,
)

from app.recipes.router import (
    RecipeRouter,
)

from app.agent.financial_agent import (
    FinancialAgent,
)

from app.ai.result_composer import (
    ResultComposer,
)

from app.ai.understanding import (
    UnderstandingService,
)

from app.application.action_executor import (
    ActionExecutor,
)

from app.application.mvp_response_formatter import (
    MVPResponseFormatter,
)

from app.contracts.action_plan import (
    ActionPlan,
)

from app.contracts.financial_agent import (
    FinancialAgentExecutionResult,
)

from app.contracts.results import (
    PlanExecutionResult,
)

from app.recipes.learning_repository import (
    LearningRunRepository,
)


@dataclass(frozen=True)
class ChatResult:

    message: str

    reply: str

    route: str

    route_confidence: float

    route_reason: str

    agent_task: str | None

    plan: ActionPlan | None

    execution: (
        PlanExecutionResult
        | FinancialAgentExecutionResult
        | RecipeExecutionResult
        | None
    )

    response_source: str

    # Only populated for successful
    # Financial Agent executions.
    feedback_run_id: str | None = None


class ChatOrchestrator:

    def __init__(
        self,
        understanding:
            UnderstandingService | None = None,



        executor:
            ActionExecutor | None = None,

        conversation_reasoner:
            ConversationReasoner | None = None,

        conversation_memory:
            ConversationMemory | None = None,

        friendly_conversation:
            FriendlyConversationService | None = None,

        financial_agent:
            FinancialAgent | None = None,

        result_composer:
            ResultComposer | None = None,

        fallback_formatter:
            MVPResponseFormatter | None = None,

        learning_repository:
            LearningRunRepository | None = None,

        recipe_router:
            RecipeRouter | None = None,

        recipe_executor:
            RecipeExecutor | None = None,

        recipe_result_composer:
            RecipeResultComposer | None = None,
    ):

        self.recipe_router = (
            recipe_router
            or RecipeRouter()
        )

        self.conversation_reasoner = (
            conversation_reasoner
            or ConversationReasoner()
        )

        self.conversation_memory = (
            conversation_memory
            or ConversationMemory(
                max_recent_turns=6,
            )
        )

        self.friendly_conversation = (
            friendly_conversation
            or FriendlyConversationService()
        )

        self.recipe_executor = (
            recipe_executor
            or RecipeExecutor()
        )

        self.recipe_result_composer = (
            recipe_result_composer
            or RecipeResultComposer()
        )

        self.understanding = (
            understanding
            or UnderstandingService()
        )

        self.executor = (
            executor
            or ActionExecutor()
        )

        self.financial_agent = (
            financial_agent
            or FinancialAgent()
        )

        self.result_composer = (
            result_composer
            or ResultComposer()
        )

        self.fallback_formatter = (
            fallback_formatter
            or MVPResponseFormatter()
        )

        self.learning_repository = (
            learning_repository
            or LearningRunRepository()
        )

    # =====================================================
    # HANDLE
    # =====================================================

    def handle(
        self,
        message: str,
    ) -> ChatResult:

        original_message = (
            message.strip()
        )

        if not original_message:
            raise ValueError(
                "Message cannot be empty."
            )

        # =========================================
        # FRIENDLY / SOCIAL FAST PATH
        #
        # Pure social messages should not pay the
        # latency/token cost of the financial pipeline.
        # =========================================

        friendly_reply = (
            self.friendly_conversation
            .try_reply(
                original_message
            )
        )

        if friendly_reply is not None:

            result = ChatResult(
                message=original_message,

                reply=(
                    friendly_reply.reply
                ),

                route="social",

                route_confidence=1.0,

                route_reason=(
                    "Matched deterministic "
                    "friendly-conversation intent: "
                    f"{friendly_reply.intent}"
                ),

                agent_task=None,

                plan=None,

                execution=None,

                response_source=(
                    "friendly_conversation"
                ),
            )

            self._remember_turn(
                user_message=(
                    original_message
                ),
                result=result,
            )

            return result

        # =========================================
        # CONVERSATION REASONING
        # =========================================

        conversation_context = (
            self.conversation_memory
            .context()
        )

        try:

            resolution = (
                self.conversation_reasoner
                .resolve(
                    message=original_message,
                    conversation_context=(
                        conversation_context
                    ),
                )
            )

            effective_message = (
                resolution
                .resolved_message
                .strip()
            )

            print(
                "\n[Conversation Reasoner]"
            )

            print(
                f"Original: {original_message}"
            )

            print(
                f"Resolved: {effective_message}"
            )

            print(
                f"Relation: {resolution.relation}"
            )

            print(
                f"Used context: "
                f"{resolution.used_context}"
            )

            if resolution.reference_summary:
                print(
                    "Reference: "
                    f"{resolution.reference_summary}"
                )

        except Exception as exc:

            # Conversation reasoning should never
            # make the whole assistant unavailable.
            print(
                "\n[Conversation Reasoner] "
                "Fallback:"
            )

            print(
                f"{type(exc).__name__}: {exc}"
            )

            effective_message = (
                original_message
            )

        # =========================================
        # NORMAL MIZAN PIPELINE
        # =========================================

        result = self._handle_core(
            effective_message
        )

        # The UI should still show the message
        # exactly as the user originally wrote it.
        result = replace(
            result,
            message=original_message,
        )

        # =========================================
        # UPDATE WORKING MEMORY
        # =========================================

        self._remember_turn(
            user_message=(
                original_message
            ),
            result=result,
        )

        return result

    def _remember_turn(
        self,
        *,
        user_message: str,
        result: ChatResult,
    ) -> None:

        try:

            self.conversation_memory.remember(
                user_message=(
                    user_message
                ),
                assistant_reply=(
                    result.reply
                ),
                response_source=(
                    result.response_source
                ),
                plan=(
                    result.plan
                ),
                execution=(
                    result.execution
                ),
            )

        except Exception as exc:

            print(
                "[Conversation Memory] "
                "Could not store turn:"
            )

            print(
                f"{type(exc).__name__}: {exc}"
            )

    def _handle_core(
        self,
        message: str,
    ) -> ChatResult:

        conversation_context = (
            self.conversation_memory
            .context()
        )

        return self._handle_once(
            message=message,
            conversation_context=(
                conversation_context
            ),
        )

    def _handle_once(
        self,
        message: str,
        conversation_context:
            dict | None = None,
    ) -> ChatResult:

        message = message.strip()

        if not message:

            raise ValueError(
                "Message cannot be empty."
            )


        # =========================================================
        # LEARNED RECIPE FAST PATH
        # =========================================================

        recipe_match = (
            self.recipe_router
            .match(
                message
            )
        )

        if recipe_match is not None:

            print(
                "\n[Recipe Router]"
            )

            print(
                "Matched:",
                recipe_match.recipe_name,
            )

            print(
                "Score:",
                recipe_match.score,
            )

            recipe_execution = (
                self.recipe_executor
                .execute_by_name(
                    recipe_name=(
                        recipe_match
                        .recipe_name
                    ),

                    user_message=message,
                )
            )

            # -----------------------------------------------------
            # SUCCESS
            # -----------------------------------------------------

            if (
                recipe_execution.status
                == "completed"
            ):

                try:

                    reply = (
                        self.recipe_result_composer
                        .compose(
                            user_message=message,
                            execution=(
                                recipe_execution
                            ),
                        )
                    )

                    response_source = (
                        "recipe_result_composer"
                    )

                except Exception as exc:

                    print(
                        "[Recipe Composer] "
                        "fallback:"
                    )

                    print(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

                    reply = (
                        self.recipe_result_composer
                        .fallback(
                            user_message=message,
                            execution=(
                                recipe_execution
                            ),
                        )
                    )

                    response_source = (
                        "recipe_deterministic_fallback"
                    )

                try:

                    self.recipe_executor.recipe_repository.record_success(
                        recipe_match.recipe_id
                    )

                except Exception:

                    pass

                feedback_run_id = None

                try:

                    feedback_run_id = (
                        self.learning_repository
                        .create_recipe_run(
                            user_message=message,

                            answer=reply,

                            execution=(
                                recipe_execution
                            ),

                            recipe_id=(
                                recipe_match
                                .recipe_id
                            ),

                            route_confidence=(
                                recipe_match
                                .score
                            ),

                            route_reason=(
                                "Matched active learned recipe: "
                                f"{recipe_match.recipe_name}"
                            ),
                        )
                    )

                except Exception as exc:

                    print(
                        "[Recipe Feedback] "
                        "Could not create feedback run:"
                    )

                    print(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

                return ChatResult(
                    message=message,

                    reply=reply,

                    route="recipe",

                    route_confidence=(
                        recipe_match.score
                    ),

                    route_reason=(
                        "Matched active learned recipe: "
                        f"{recipe_match.recipe_name}"
                    ),

                    agent_task=None,

                    plan=None,

                    execution=(
                        recipe_execution
                    ),

                    response_source=(
                        response_source
                    ),

                    feedback_run_id=(
                        feedback_run_id
                    ),
                )

            # -----------------------------------------------------
            # RECIPE COULD NOT EXECUTE SAFELY
            #
            # Do NOT answer from it.
            # Fall through to normal Understanding.
            # -----------------------------------------------------

            print(
                "[Recipe Router] "
                "Fallback to normal routing:"
            )

            print(
                recipe_execution
                .fallback_reason
            )



        understanding_result = (
            self.understanding
            .understand(
                message=message,
                conversation_context=(
                    conversation_context
                ),
            )
        )

        decision = (
            understanding_result.data
        )

        # =================================================
        # FINANCIAL AGENT
        # =================================================

        if decision.route == "agent":

            return (
                self._run_financial_agent(
                    message=message,

                    route_confidence=(
                        decision
                        .route_confidence
                    ),

                    route_reason=(
                        decision
                        .route_reason
                    ),

                    agent_task=(
                        decision
                        .agent_task
                    ),
                )
            )

        # =================================================
        # LEGACY
        # =================================================

        plan = decision.plan

        if plan is None:

            raise RuntimeError(
                "Legacy route returned "
                "no ActionPlan."
            )

        status = getattr(
            plan.status,
            "value",
            plan.status,
        )

        # =================================================
        # CLARIFICATION
        # =================================================

        if (
            status
            == "needs_clarification"
        ):

            clarification = (
                plan.clarification
            )

            if clarification is not None:

                reason = getattr(
                    clarification,
                    "reason",
                    None,
                )

                reply = (
                    reason
                    or (
                        "أحتاج توضيحًا إضافيًا "
                        "لتنفيذ طلبك."
                    )
                )

            else:

                reply = (
                    "أحتاج توضيحًا إضافيًا "
                    "لتنفيذ طلبك."
                )

            return ChatResult(
                message=message,
                reply=reply,

                route="legacy",

                route_confidence=(
                    decision
                    .route_confidence
                ),

                route_reason=(
                    decision
                    .route_reason
                ),

                agent_task=None,

                plan=plan,

                execution=None,

                response_source=(
                    "clarification"
                ),
            )

        # =================================================
        # UNSUPPORTED
        # =================================================

        if status == "unsupported":

            return ChatResult(
                message=message,

                reply=(
                    "هذا الطلب غير مدعوم حاليًا."
                ),

                route="legacy",

                route_confidence=(
                    decision
                    .route_confidence
                ),

                route_reason=(
                    decision
                    .route_reason
                ),

                agent_task=None,

                plan=plan,

                execution=None,

                response_source=(
                    "unsupported"
                ),
            )

        # =================================================
        # READY LEGACY PLAN
        # =================================================

        if status != "ready":

            raise RuntimeError(
                "Unexpected ActionPlan status: "
                f"{status}"
            )

        return (
            self._run_legacy(
                message=message,

                plan=plan,

                route_confidence=(
                    decision
                    .route_confidence
                ),

                route_reason=(
                    decision
                    .route_reason
                ),
            )
        )

    # =====================================================
    # FINANCIAL AGENT PATH
    # =====================================================

    def _run_financial_agent(
        self,
        *,
        message: str,
        route_confidence: float,
        route_reason: str,
        agent_task: str | None,
    ) -> ChatResult:

        if not agent_task:

            raise RuntimeError(
                "Financial Agent route "
                "requires agent_task."
            )

        print(
            "\n"
            "[Chat Orchestrator]"
        )

        print(
            "Route: financial_agent"
        )

        print(
            f"Task: {agent_task}"
        )

        try:

            execution = (
                self.financial_agent
                .run(
                    user_message=message,
                    task=agent_task,
                )
            )

            # =============================================
            # LEARNING RUN
            #
            # Only completed Agent executions are eligible
            # for user feedback and future learning.
            #
            # Logging failure must NEVER break the actual
            # financial answer.
            # =============================================

            feedback_run_id = None

            if (
                execution.status
                == "completed"
            ):

                try:

                    feedback_run_id = (
                        self.learning_repository
                        .create_agent_run(
                            user_message=message,

                            agent_task=(
                                agent_task
                            ),

                            route_confidence=(
                                route_confidence
                            ),

                            route_reason=(
                                route_reason
                            ),

                            answer=(
                                execution.answer
                            ),

                            execution=(
                                execution
                                .model_dump(
                                    mode="json"
                                )
                            ),
                        )
                    )

                    print(
                        "\n"
                        "[Recipe Learning]"
                    )

                    print(
                        "Feedback run created:",
                        feedback_run_id,
                    )

                except Exception as exc:

                    print(
                        "\n"
                        "[recipe_learning] "
                        "failed to save run:"
                    )

                    print(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

            return ChatResult(
                message=message,

                reply=(
                    execution.answer
                ),

                route="agent",

                route_confidence=(
                    route_confidence
                ),

                route_reason=(
                    route_reason
                ),

                agent_task=(
                    agent_task
                ),

                plan=None,

                execution=execution,

                response_source=(
                    "financial_agent"
                ),

                feedback_run_id=(
                    feedback_run_id
                ),
            )

        except Exception as exc:

            print(
                "\n"
                "[financial_agent] "
                "execution failed:"
            )

            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            return ChatResult(
                message=message,

                reply=(
                    "تعذر إكمال التحليل المالي "
                    "حاليًا. حاول مرة أخرى."
                ),

                route="agent",

                route_confidence=(
                    route_confidence
                ),

                route_reason=(
                    route_reason
                ),

                agent_task=(
                    agent_task
                ),

                plan=None,

                execution=None,

                response_source=(
                    "financial_agent_error"
                ),
            )

    # =====================================================
    # LEGACY PATH
    # =====================================================

    def _run_legacy(
        self,
        *,
        message: str,
        plan: ActionPlan,
        route_confidence: float,
        route_reason: str,
    ) -> ChatResult:

        execution = (
            self.executor
            .execute(
                plan=plan,
                user_message=message,
            )
        )

        try:

            reply = (
                self.result_composer
                .compose(
                    user_message=message,
                    plan=plan,
                    execution=execution,
                )
            )

            response_source = (
                "grok_result_composer"
            )

        except Exception as exc:

            print(
                "[result_composer] "
                "fallback triggered:"
            )

            print(
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            reply = (
                self.fallback_formatter
                .format(
                    plan=plan,
                    execution=execution,
                    user_message=message,
                )
            )

            response_source = (
                "deterministic_fallback"
            )

        return ChatResult(
            message=message,

            reply=reply,

            route="legacy",

            route_confidence=(
                route_confidence
            ),

            route_reason=(
                route_reason
            ),

            agent_task=None,

            plan=plan,

            execution=execution,

            response_source=(
                response_source
            ),
        )