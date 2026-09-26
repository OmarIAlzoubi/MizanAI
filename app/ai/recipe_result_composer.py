import json
import re

from pathlib import Path
from typing import Any

from app.ai.grok_client import (
    GrokClient,
)

from app.contracts.recipe_execution import (
    RecipeExecutionResult,
)

from app.core.config import (
    get_settings,
)


PROMPT_PATH = (
    Path(__file__).resolve().parent
    / "prompts"
    / "recipe_result_composer.txt"
)


class RecipeResultComposer:

    def __init__(
        self,
        grok_client:
            GrokClient | None = None,
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
    # COMPOSE
    # =====================================================

    def compose(
        self,
        *,
        user_message: str,
        execution:
            RecipeExecutionResult,
    ) -> str:

        if (
            execution.status
            != "completed"
        ):

            raise ValueError(
                "Recipe result composer "
                "requires completed execution."
            )

        payload = {
            "user_message":
                user_message,

            "parameters":
                execution.parameters,

            "coverage_end_local_date":
                execution
                .coverage_end_local_date,

            "verified_steps":
                [
                    {
                        "operation":
                            step.operation,

                        "purpose":
                            step.purpose,

                        "rows":
                            self._clean_values(
                                step.rows
                            ),
                    }

                    for step
                    in execution.steps

                    if step.status == "ok"
                ],
        }

        user_prompt = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        answer = (
            self.grok.generate_text(
                system_prompt=(
                    self.system_prompt
                ),

                user_prompt=(
                    user_prompt
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
                    "mizan-recipe-result-v1"
                ),
            )
        )

        answer = (
            answer.strip()
        )

        if not answer:

            raise RuntimeError(
                "Recipe result composer "
                "returned an empty answer."
            )

        return answer

    # =====================================================
    # DETERMINISTIC FALLBACK
    # =====================================================

    def fallback(
        self,
        *,
        user_message: str,
        execution:
            RecipeExecutionResult,
    ) -> str:

        comparison = None

        merchant_rows = []

        for step in execution.steps:

            if (
                step.operation
                == "compare_spending_periods"
                and step.rows
            ):

                comparison = (
                    step.rows[0]
                )

            if (
                step.operation
                == "rank_dimension_delta"
                and "merchant"
                in step.purpose.lower()
            ):

                merchant_rows = (
                    step.rows
                )

        if comparison is None:

            return (
                "تم تنفيذ التحليل، "
                "لكن تعذر صياغة النتيجة حاليًا."
            )

        target = round(
            float(
                comparison.get(
                    "target_sar",
                    0,
                )
            ),
            2,
        )

        previous = round(
            float(
                comparison.get(
                    "comparison_sar",
                    0,
                )
            ),
            2,
        )

        delta = round(
            float(
                comparison.get(
                    "delta_sar",
                    0,
                )
            ),
            2,
        )

        arabic = bool(
            re.search(
                r"[\u0600-\u06FF]",
                user_message,
            )
        )

        contributors = [
            row
            for row
            in merchant_rows
            if float(
                row.get(
                    "delta_sar",
                    0,
                )
            ) > 0
        ][
            :3
        ]

        if arabic:

            if delta > 0:

                text = (
                    f"نعم، صرفك ارتفع بحوالي "
                    f"{delta:,.2f} ريال؛ "
                    f"من {previous:,.2f} إلى "
                    f"{target:,.2f} ريال."
                )

            elif delta < 0:

                text = (
                    f"فعليًا صرفك انخفض بحوالي "
                    f"{abs(delta):,.2f} ريال؛ "
                    f"من {previous:,.2f} إلى "
                    f"{target:,.2f} ريال."
                )

            else:

                text = (
                    "صرفك في الفترتين متساوٍ تقريبًا."
                )

            if contributors:

                items = []

                for row in contributors:

                    name = (
                        row.get(
                            "dimension_value",
                            "(unknown)",
                        )
                    )

                    value = round(
                        float(
                            row.get(
                                "delta_sar",
                                0,
                            )
                        ),
                        2,
                    )

                    items.append(
                        f"{name} "
                        f"(+{value:,.2f} ريال)"
                    )

                text += (
                    " أبرز الزيادات كانت من: "
                    + "، ".join(
                        items
                    )
                    + "."
                )

            if (
                execution
                .coverage_end_local_date
            ):

                text += (
                    " التحليل مبني على العمليات "
                    "المسجلة حتى "
                    f"{execution.coverage_end_local_date}."
                )

            return text

        if delta > 0:

            text = (
                f"Your spending increased by "
                f"SAR {delta:,.2f}, from "
                f"SAR {previous:,.2f} to "
                f"SAR {target:,.2f}."
            )

        elif delta < 0:

            text = (
                f"Your spending actually decreased "
                f"by SAR {abs(delta):,.2f}, from "
                f"SAR {previous:,.2f} to "
                f"SAR {target:,.2f}."
            )

        else:

            text = (
                "Your spending was essentially "
                "unchanged between the periods."
            )

        return text

    # =====================================================
    # JSON CLEANUP
    # =====================================================

    def _clean_values(
        self,
        value: Any,
    ) -> Any:

        if isinstance(
            value,
            float,
        ):

            return round(
                value,
                2,
            )

        if isinstance(
            value,
            list,
        ):

            return [
                self._clean_values(
                    item
                )
                for item in value
            ]

        if isinstance(
            value,
            dict,
        ):

            return {
                key:
                    self._clean_values(
                        item
                    )

                for key, item
                in value.items()
            }

        return value