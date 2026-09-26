import json

from datetime import datetime
from zoneinfo import ZoneInfo

from pathlib import Path
from typing import Any

from app.ai.grok_client import (
    GrokClient,
    StructuredLLMResult,
)

from app.application.plan_compiler import (
    compile_llm_plan,
)

from app.contracts.llm_plan import (
    LLMActionPlan,
)

from app.contracts.understanding import (
    UnderstandingDecision,
)

from app.core.config import (
    get_settings,
)


PROMPT_PATH = (
    Path(__file__).resolve().parent
    / "prompts"
    / "understanding.txt"
)


class UnderstandingService:

    def __init__(
        self,
        grok_client: GrokClient | None = None,
    ):

        self.grok = (
            grok_client
            or GrokClient()
        )

        self.settings = (
            get_settings()
        )

        self.system_prompt = (
            PROMPT_PATH
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

    # =====================================================
    # UNDERSTAND
    # =====================================================

    def understand(
        self,
        *,
        message: str,
        conversation_context: (
            dict[str, Any]
            | None
        ) = None,
    ) -> StructuredLLMResult[
        UnderstandingDecision
    ]:

        message = message.strip()

        if not message:

            raise ValueError(
                "message cannot be empty."
            )

        context = (
            conversation_context
            or {}
        )

        now_local = datetime.now(
            ZoneInfo(
                self.settings.default_timezone
            )
        )

        payload = {

            "user_message":
                message,

            "environment": {
                "default_currency":
                    self.settings.default_currency,

                "timezone":
                    self.settings.default_timezone,

                "local_now":
                    now_local.isoformat(
                        timespec="seconds"
                    ),

                "local_date":
                    now_local.date().isoformat(),
            },

            "conversation_context":
                context,
        }

        user_prompt = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        # =================================================
        # ONE LLM CALL:
        #
        # semantic understanding
        # +
        # capability routing
        # =================================================

        raw_result = (
            self.grok
            .generate_structured(

                system_prompt=(
                    self.system_prompt
                ),

                user_prompt=(
                    user_prompt
                ),

                response_model=(
                    LLMActionPlan
                ),

                model=(
                    self.settings
                    .xai_understanding_model
                ),

                reasoning_effort=(
                    self.settings
                    .xai_understanding_reasoning
                ),

                prompt_cache_key=(
                    "mizan-understanding-v3"
                ),
            )
        )

        llm_plan = (
            raw_result.data
        )

        # =================================================
        # CAPABILITY GATE
        # =================================================

        print(
            "\n"
            "[Capability Gate]"
        )

        print(
            json.dumps(
                {
                    "route":
                        llm_plan.route,

                    "confidence":
                        llm_plan
                        .route_confidence,

                    "reason":
                        llm_plan
                        .route_reason,

                    "agent_task":
                        llm_plan
                        .agent_task,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        # =================================================
        # AGENT ROUTE
        #
        # No fake unsupported ActionPlan.
        # No legacy compilation.
        # =================================================

        if llm_plan.route == "agent":

            decision = (
                UnderstandingDecision(

                    route="agent",

                    route_confidence=(
                        llm_plan
                        .route_confidence
                    ),

                    route_reason=(
                        llm_plan
                        .route_reason
                    ),

                    agent_task=(
                        llm_plan
                        .agent_task
                    ),

                    plan=None,
                )
            )

            return StructuredLLMResult(

                data=decision,

                usage=raw_result.usage,

                model=raw_result.model,

                latency_ms=(
                    raw_result.latency_ms
                ),
            )

        # =================================================
        # LEGACY ROUTE
        # =================================================

        if llm_plan.status is None:

            raise RuntimeError(
                "Legacy route returned "
                "no ActionPlan status."
            )

        compiled_plan = (
            compile_llm_plan(
                llm_plan
            )
        )

        decision = (
            UnderstandingDecision(

                route="legacy",

                route_confidence=(
                    llm_plan
                    .route_confidence
                ),

                route_reason=(
                    llm_plan
                    .route_reason
                ),

                agent_task=None,

                plan=compiled_plan,
            )
        )

        return StructuredLLMResult(

            data=decision,

            usage=raw_result.usage,

            model=raw_result.model,

            latency_ms=(
                raw_result.latency_ms
            ),
        )