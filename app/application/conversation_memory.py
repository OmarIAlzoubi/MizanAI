from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _dump(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return value.model_dump(
            mode="json"
        )

    if isinstance(value, dict):
        return {
            key: _dump(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _dump(item)
            for item in value
        ]

    return _enum_value(value)


class ConversationMemory:
    """
    Small process-local working memory for MizanAI.

    Goals:
    - help resolve conversational references
    - keep context compact
    - avoid storing full SQL/tool traces
    - stay route-agnostic

    This is intentionally NOT long-term user memory.
    It resets when the Python process restarts.
    """

    def __init__(
        self,
        *,
        max_recent_turns: int = 4,
        max_recent_periods: int = 5,
        max_text_chars: int = 800,
    ):
        self.max_recent_turns = (
            max_recent_turns
        )

        self.max_recent_periods = (
            max_recent_periods
        )

        self.max_text_chars = (
            max_text_chars
        )

        self._lock = RLock()

        self.reset()

    # =====================================================
    # PUBLIC API
    # =====================================================

    def reset(self) -> None:
        with self._lock:
            self._turn_count = 0

            self._last_user_message = None
            self._last_assistant_reply = None
            self._last_response_source = None

            self._last_financial_query = None

            self._recent_periods = []
            self._recent_turns = []

    def context(self) -> dict[str, Any]:
        with self._lock:
            if self._turn_count == 0:
                return {}

            return deepcopy(
                {
                    "turn_count":
                        self._turn_count,

                    "last_turn": {
                        "user_message":
                            self._last_user_message,

                        "assistant_reply":
                            self._last_assistant_reply,

                        "response_source":
                            self._last_response_source,
                    },

                    "last_financial_query":
                        self._last_financial_query,

                    "recent_periods":
                        self._recent_periods,

                    "recent_turns":
                        self._recent_turns,
                }
            )

    def remember(
        self,
        *,
        user_message: str,
        assistant_reply: str,
        response_source: str | None,
        plan: Any = None,
        execution: Any = None,
    ) -> None:

        user_message = (
            user_message
            .strip()
        )

        assistant_reply = (
            assistant_reply
            .strip()
        )

        with self._lock:
            self._turn_count += 1

            self._last_user_message = (
                self._clip(
                    user_message
                )
            )

            self._last_assistant_reply = (
                self._clip(
                    assistant_reply
                )
            )

            self._last_response_source = (
                response_source
            )

            query_memory = (
                self._extract_query_memory(
                    plan=plan,
                    execution=execution,
                )
            )

            if query_memory is not None:
                self._last_financial_query = (
                    query_memory
                )

                period = (
                    query_memory
                    .get("period")
                )

                if period:
                    self._append_period(
                        period
                    )

            else:
                recipe_memory = (
                    self._extract_recipe_memory(
                        execution
                    )
                )

                if recipe_memory is not None:
                    self._last_financial_query = (
                        recipe_memory
                    )

                    period = (
                        recipe_memory
                        .get("period")
                    )

                    if period:
                        self._append_period(
                            period
                        )

            self._recent_turns.append(
                {
                    "user_message":
                        self._clip(
                            user_message
                        ),

                    "assistant_reply":
                        self._clip(
                            assistant_reply
                        ),

                    "response_source":
                        response_source,
                }
            )

            self._recent_turns = (
                self._recent_turns[
                    -self.max_recent_turns:
                ]
            )

    # =====================================================
    # INTERNAL HELPERS
    # =====================================================

    def _clip(
        self,
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = value.strip()

        if (
            len(value)
            <= self.max_text_chars
        ):
            return value

        return (
            value[
                :self.max_text_chars
            ]
            + "…"
        )

    def _append_period(
        self,
        period: dict[str, Any],
    ) -> None:

        normalized = deepcopy(
            period
        )

        if (
            self._recent_periods
            and
            self._recent_periods[-1]
            == normalized
        ):
            return

        self._recent_periods.append(
            normalized
        )

        self._recent_periods = (
            self._recent_periods[
                -self.max_recent_periods:
            ]
        )

    @staticmethod
    def _extract_query_memory(
        *,
        plan: Any,
        execution: Any,
    ) -> dict[str, Any] | None:

        if plan is None:
            return None

        actions = getattr(
            plan,
            "actions",
            None,
        )

        if not actions:
            return None

        query_action = None

        for action in reversed(actions):
            action_type = _enum_value(
                getattr(
                    action,
                    "type",
                    None,
                )
            )

            if (
                action_type
                == "query_financial_data"
            ):
                query_action = action
                break

        if query_action is None:
            return None

        parameters = getattr(
            query_action,
            "parameters",
            None,
        )

        if parameters is None:
            return None

        metric = _enum_value(
            getattr(
                parameters,
                "metric",
                None,
            )
        )

        period = _dump(
            getattr(
                parameters,
                "period",
                None,
            )
        )

        filters = _dump(
            getattr(
                parameters,
                "filters",
                None,
            )
        )

        action_id = getattr(
            query_action,
            "action_id",
            None,
        )

        result_data = None

        execution_actions = getattr(
            execution,
            "actions",
            None,
        )

        if execution_actions:
            for result in execution_actions:
                if (
                    getattr(
                        result,
                        "action_id",
                        None,
                    )
                    == action_id
                ):
                    result_data = _dump(
                        getattr(
                            result,
                            "data",
                            None,
                        )
                    )

                    break

        return {
            "metric":
                metric,

            "period":
                period,

            "filters":
                filters,

            "result":
                result_data,
        }

    @staticmethod
    def _extract_recipe_memory(
        execution: Any,
    ) -> dict[str, Any] | None:

        payload = _dump(
            execution
        )

        if not isinstance(
            payload,
            dict,
        ):
            return None

        execution_type = (
            payload.get("type")
        )

        if (
            execution_type
            != "recipe_execution"
        ):
            return None

        parameters = (
            payload.get("parameters")
            or {}
        )

        target_period = (
            parameters.get(
                "target_period"
            )
        )

        if not isinstance(
            target_period,
            dict,
        ):
            return None

        start = (
            target_period.get("start")
            or target_period.get(
                "requested_start"
            )
        )

        end = (
            target_period.get("end")
            or target_period.get(
                "requested_end"
            )
        )

        period = None

        if start and end:
            period = {
                "type":
                    "absolute_range",

                "offset":
                    0,

                "days":
                    None,

                "months":
                    None,

                "start_date":
                    start,

                "end_date":
                    end,
            }

        return {
            "metric":
                "spending",

            "period":
                period,

            "filters":
                None,

            "result": {
                "recipe_name":
                    payload.get(
                        "recipe_name"
                    )
            },
        }
