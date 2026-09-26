import json
import re

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.ai.grok_client import (
    GrokClient,
)

from app.agent.finance_query_tool import (
    FinanceQueryTool,
)

from app.contracts.financial_agent import (
    FinancialAgentDecision,
    FinancialAgentExecutionResult,
    FinancialAgentStep,
)

from app.core.config import (
    get_settings,
)


PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "ai"
    / "prompts"
    / "financial_agent.txt"
)


class FinancialAgent:

    DEFAULT_MAX_ITERATIONS = 6

    def __init__(
        self,
        grok_client: GrokClient | None = None,
        query_tool: FinanceQueryTool | None = None,
        max_iterations: int = (
            DEFAULT_MAX_ITERATIONS
        ),
    ):

        self.grok = (
            grok_client
            or GrokClient()
        )

        self.query_tool = (
            query_tool
            or FinanceQueryTool(
                max_rows=50,
                timeout_seconds=2.0,
            )
        )

        self.settings = (
            get_settings()
        )

        self.max_iterations = (
            max_iterations
        )

        self.system_prompt = (
            PROMPT_PATH
            .read_text(
                encoding="utf-8"
            )
            .strip()
        )

        # Prefer the stronger model for open-ended
        # financial investigation.
        self.model = getattr(
            self.settings,
            "xai_complex_model",
            self.settings.xai_understanding_model,
        )

        self.reasoning_effort = getattr(
            self.settings,
            "xai_complex_reasoning",
            self.settings.xai_understanding_reasoning,
        )

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
        *,
        user_message: str,
        task: str,
    ) -> FinancialAgentExecutionResult:

        user_message = (
            user_message.strip()
        )

        task = task.strip()

        if not user_message:
            raise ValueError(
                "user_message cannot be empty."
            )

        if not task:
            raise ValueError(
                "task cannot be empty."
            )

        steps: list[
            FinancialAgentStep
        ] = []

        # Normalized SQL -> first step number
        #
        # This is deliberately enforced in Python.
        # The LLM is also instructed not to repeat
        # queries, but correctness should not depend
        # only on prompt compliance.
        seen_queries: dict[
            str,
            int,
        ] = {}

        environment = (
            self._build_environment()
        )

        for iteration in range(
            1,
            self.max_iterations + 1,
        ):

            payload = {
                "user_message":
                    user_message,

                "agent_task":
                    task,

                "environment":
                    environment,

                "previous_steps": [
                    step.model_dump(
                        mode="json"
                    )
                    for step
                    in steps
                ],
            }

            user_prompt = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )

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
                        FinancialAgentDecision
                    ),

                    model=(
                        self.model
                    ),

                    reasoning_effort=(
                        self.reasoning_effort
                    ),

                    # Prompt changed substantially:
                    # delta analysis, truncation awareness,
                    # evidence authority, duplicate handling.
                    prompt_cache_key=(
                        "mizan-financial-agent-v2"
                    ),
                )
            )

            decision = (
                raw_result.data
            )

            # =============================================
            # FINAL
            # =============================================

            if decision.action == "final":

                return (
                    FinancialAgentExecutionResult(
                        status="completed",
                        task=task,
                        answer=decision.answer,
                        steps=steps,
                    )
                )

            # =============================================
            # QUERY
            # =============================================

            sql = (
                decision.sql
                or ""
            ).strip()

            purpose = (
                decision.purpose
                or "Financial analysis"
            )

            print(
                f"\n[Financial Agent] "
                f"Step {iteration}"
            )

            print(
                f"Purpose: {purpose}"
            )

            print(
                "SQL:"
            )

            print(
                sql
            )

            # =============================================
            # DUPLICATE QUERY PROTECTION
            # =============================================

            normalized_sql = (
                self._normalize_sql(
                    sql
                )
            )

            if normalized_sql in seen_queries:

                first_step = (
                    seen_queries[
                        normalized_sql
                    ]
                )

                error_message = (
                    "Duplicate query rejected. "
                    f"The same SQL was already attempted "
                    f"in step {first_step}. "
                    "Choose a different analytical "
                    "approach or query."
                )

                step = FinancialAgentStep(
                    step=iteration,
                    purpose=purpose,
                    sql=sql,
                    status="error",
                    columns=[],
                    rows=[],
                    row_count=0,
                    truncated=False,
                    error=error_message,
                )

                steps.append(
                    step
                )

                print(
                    "Query rejected:"
                )

                print(
                    error_message
                )

                continue

            # Register BEFORE execution.
            #
            # This means even a failed query cannot simply
            # be submitted again unchanged on the next turn.
            seen_queries[
                normalized_sql
            ] = iteration

            # =============================================
            # EXECUTE VERIFIED QUERY
            # =============================================

            try:

                query_result = (
                    self.query_tool
                    .execute(
                        sql
                    )
                )

                step = FinancialAgentStep(
                    step=iteration,
                    purpose=purpose,
                    sql=sql,
                    status="ok",
                    columns=(
                        query_result.columns
                    ),
                    rows=(
                        query_result.rows
                    ),
                    row_count=(
                        query_result.row_count
                    ),
                    truncated=(
                        query_result.truncated
                    ),
                    error=None,
                )

                print(
                    "Result rows:",
                    query_result.row_count,
                )

                print(
                    "Truncated:",
                    query_result.truncated,
                )

                if query_result.truncated:

                    print(
                        "Note: result set exceeded "
                        "the row limit. The agent "
                        "must treat this as incomplete."
                    )

            except Exception as exc:

                step = FinancialAgentStep(
                    step=iteration,
                    purpose=purpose,
                    sql=sql,
                    status="error",
                    columns=[],
                    rows=[],
                    row_count=0,
                    truncated=False,
                    error=(
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                )

                print(
                    "Query error:"
                )

                print(
                    step.error
                )

            steps.append(
                step
            )

        # =================================================
        # ITERATION LIMIT
        # =================================================

        return FinancialAgentExecutionResult(
            status="failed",
            task=task,
            answer=(
                "لم أتمكن من إكمال التحليل بثقة "
                "ضمن عدد خطوات التحليل المتاح."
            ),
            steps=steps,
        )

    # =====================================================
    # SQL NORMALIZATION
    # =====================================================

    @staticmethod
    def _normalize_sql(
        sql: str,
    ) -> str:

        """
        Normalize SQL only for duplicate detection.

        This is NOT SQL validation.

        Security validation remains the responsibility
        of FinanceQueryTool / FinancialSQLGuard.

        The goal here is to detect the same query even
        when the LLM changes whitespace or casing.
        """

        normalized = (
            sql.strip()
            .rstrip(";")
        )

        # Collapse all whitespace:
        #
        # SELECT   *
        # FROM x
        #
        # becomes:
        #
        # SELECT * FROM x
        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return (
            normalized.casefold()
        )

    # =====================================================
    # ENVIRONMENT
    # =====================================================

    def _build_environment(
        self,
    ) -> dict:

        timezone_name = (
            self.settings
            .default_timezone
        )

        timezone = ZoneInfo(
            timezone_name
        )

        now = datetime.now(
            timezone
        )

        offset = (
            now.utcoffset()
        )

        if offset is None:

            sqlite_offset = (
                "+00:00"
            )

        else:

            total_minutes = int(
                offset.total_seconds()
                // 60
            )

            sign = (
                "+"
                if total_minutes >= 0
                else "-"
            )

            total_minutes = abs(
                total_minutes
            )

            hours, minutes = divmod(
                total_minutes,
                60,
            )

            sqlite_offset = (
                f"{sign}"
                f"{hours:02d}:"
                f"{minutes:02d}"
            )

        return {
            "default_currency":
                self.settings
                .default_currency,

            "timezone":
                timezone_name,

            "local_now":
                now.isoformat(
                    timespec="seconds"
                ),

            "sqlite_utc_offset_modifier":
                sqlite_offset,
        }