import json
import os

from pathlib import Path

from app.ai.grok_client import (
    GrokClient,
)

from app.contracts.action_plan import (
    ActionPlan,
)

from app.contracts.results import (
    PlanExecutionResult,
)


class ResultComposer:

    def __init__(
        self,
        client: GrokClient | None = None,
    ):
        self.client = (
            client
            or GrokClient()
        )

        # =============================================
        # MODEL CONFIGURATION
        #
        # Use the same lightweight Grok configuration
        # currently used for understanding.
        #
        # No second model is required.
        # =============================================

        self.model = os.getenv(
            "XAI_UNDERSTANDING_MODEL",
            "grok-4.3",
        )

        self.reasoning_effort = os.getenv(
            "XAI_UNDERSTANDING_REASONING",
            "none",
        )

        # =============================================
        # PROMPT
        # =============================================

        prompt_path = (
            Path(__file__)
            .resolve()
            .parent
            / "prompts"
            / "result_composer.txt"
        )

        self.system_prompt = (
            prompt_path
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

    # =================================================
    # PUBLIC
    # =================================================

    def compose(
        self,
        *,
        user_message: str,
        plan: ActionPlan,
        execution: PlanExecutionResult,
    ) -> str:

        context = (
            self._build_context(
                user_message=user_message,
                plan=plan,
                execution=execution,
            )
        )

        user_prompt = json.dumps(
            context,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        response = (
            self.client
            .generate_text(
                system_prompt=(
                    self.system_prompt
                ),
                user_prompt=(
                    user_prompt
                ),
                model=(
                    self.model
                ),
                reasoning_effort=(
                    self.reasoning_effort
                ),
            )
        )

        response = (
            response
            .strip()
        )

        if not response:
            raise RuntimeError(
                "Result composer returned "
                "an empty response."
            )

        return response

    # =================================================
    # CONTEXT BUILDER
    # =================================================

    @staticmethod
    def _build_context(
        *,
        user_message: str,
        plan: ActionPlan,
        execution: PlanExecutionResult,
    ) -> dict:

        plan_data = (
            plan.model_dump(
                mode="json"
            )
        )

        execution_data = (
            execution.model_dump(
                mode="json"
            )
        )

        # =============================================
        # RESULT INDEX
        # =============================================

        execution_by_id = {
            item["action_id"]: item
            for item
            in execution_data.get(
                "actions",
                [],
            )
        }

        # =============================================
        # CONNECT REQUESTS WITH VERIFIED RESULTS
        # =============================================

        actions = []

        for action in plan_data.get(
            "actions",
            [],
        ):

            action_id = (
                action.get(
                    "action_id"
                )
            )

            result = (
                execution_by_id
                .get(
                    action_id
                )
            )

            result_payload = None

            if result is not None:

                result_payload = {
                    "status":
                        result.get(
                            "status"
                        ),

                    "data":
                        result.get(
                            "data"
                        ),
                }

            actions.append(
                {
                    "request": {
                        "type":
                            action.get(
                                "type"
                            ),

                        "parameters":
                            action.get(
                                "parameters"
                            ),
                    },

                    "result":
                        result_payload,
                }
            )

        # =============================================
        # FINAL COMPOSER CONTEXT
        # =============================================

        return {
            "user_message":
                user_message,

            "execution_status":
                execution_data.get(
                    "status"
                ),

            "actions":
                actions,
        }