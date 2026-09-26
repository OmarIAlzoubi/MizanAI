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
    PlanCompilationError,
    compile_llm_plan,
)

from app.contracts.llm_plan import (
    LLMActionPlan,
    LLMConversationResponseAction,
    LLMQueryFinancialDataAction,
)

from app.contracts.understanding import (
    UnderstandingDecision,
)

from app.core.config import (
    get_settings,
)


# =========================================================
# ROUTING SAFETY HELPERS
# =========================================================

def _normalize_route_text(
    value: str,
) -> str:
    text = value.casefold()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ة": "ه",
    }

    for source, target in replacements.items():
        text = text.replace(
            source,
            target,
        )

    return " ".join(
        text.split()
    )


def _looks_like_latest_transaction_request(
    message: str,
) -> bool:
    """
    Conservative deterministic safeguard for a class of requests
    that the aggregate legacy query contract cannot represent
    faithfully without inventing a time period.

    The LLM still owns normal semantic routing. This helper only
    catches explicit "latest / last time / most recent" transaction
    language after the model has already produced a financial query.
    """

    text = _normalize_route_text(
        message
    )

    phrases = (
        # Arabic
        "اخر مره",
        "اخر عمليه",
        "احدث عمليه",

        # English
        "last time",
        "latest transaction",
        "most recent transaction",
        "latest purchase",
        "most recent purchase",
    )

    return any(
        phrase in text
        for phrase in phrases
    )


def _has_query_action(
    llm_plan: LLMActionPlan,
) -> bool:
    return any(
        isinstance(
            action,
            LLMQueryFinancialDataAction,
        )
        for action in llm_plan.actions
    )


def _is_read_only_legacy_plan(
    llm_plan: LLMActionPlan,
) -> bool:
    """
    Agent fallback is allowed only for read-only legacy plans.

    Never turn a malformed create/update plan into an Agent request,
    because writes must remain on the deterministic write path.
    """

    if not _has_query_action(
        llm_plan
    ):
        return False

    safe_types = (
        LLMQueryFinancialDataAction,
        LLMConversationResponseAction,
    )

    return all(
        isinstance(
            action,
            safe_types,
        )
        for action in llm_plan.actions
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
                    "mizan-understanding-v5"
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
        # DETERMINISTIC TRANSACTION-DETAIL SAFEGUARD
        #
        # The legacy query contract always requires a PeriodSpec.
        # A request such as "when was the last time I bought coffee?"
        # is an all-history transaction lookup, not a period aggregate.
        #
        # If the model still tries to express that request as a legacy
        # financial query, force the transaction-capable Agent path
        # instead of fabricating a date range.
        # =================================================

        if (
            llm_plan.route == "legacy"
            and _has_query_action(
                llm_plan
            )
            and _looks_like_latest_transaction_request(
                message
            )
        ):

            print(
                "\n"
                "[Capability Gate Override]\n"
                "Route: financial_agent\n"
                "Reason: latest transaction lookup "
                "requires transaction-level drill-down."
            )

            decision = (
                UnderstandingDecision(

                    route="agent",

                    route_confidence=(
                        llm_plan
                        .route_confidence
                    ),

                    route_reason=(
                        "Deterministic safeguard: explicit latest/"
                        "most-recent transaction lookup requires "
                        "transaction-level drill-down."
                    ),

                    agent_task=(
                        "Identify the most recent verified financial "
                        "transaction matching the user's request. "
                        "Use transaction-level data and return only "
                        "facts supported by the database."
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

        try:

            compiled_plan = (
                compile_llm_plan(
                    llm_plan
                )
            )

        except PlanCompilationError as exc:

            # =============================================
            # READ-ONLY SAFETY FALLBACK
            #
            # A malformed LLM query plan must not turn a
            # financial read into HTTP 500.
            #
            # We only fall back for read-only query plans.
            # Create/update failures are deliberately
            # re-raised so writes stay deterministic.
            # =============================================

            if not _is_read_only_legacy_plan(
                llm_plan
            ):
                raise

            print(
                "\n"
                "[Plan Compiler Fallback]\n"
                "Route: financial_agent\n"
                f"Reason: {exc}"
            )

            decision = (
                UnderstandingDecision(

                    route="agent",

                    route_confidence=(
                        llm_plan
                        .route_confidence
                    ),

                    route_reason=(
                        "Legacy read-only plan failed deterministic "
                        "validation; routed to Financial Agent rather "
                        "than returning an internal server error."
                    ),

                    agent_task=(
                        "Resolve the user's read-only financial "
                        "request using verified financial data. "
                        "Inspect transaction-level records as needed "
                        "and do not invent missing facts."
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