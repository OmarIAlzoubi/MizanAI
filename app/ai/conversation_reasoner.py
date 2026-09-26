from __future__ import annotations

import json

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.ai.grok_client import (
    GrokClient,
)
from app.contracts.conversation import (
    ConversationResolution,
)
from app.core.config import (
    get_settings,
)


PROMPT_PATH = (
    Path(__file__).resolve().parent
    / "prompts"
    / "conversation_reasoner.txt"
)


class ConversationReasoner:

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

    def resolve(
        self,
        *,
        message: str,
        conversation_context:
            dict[str, Any] | None = None,
    ) -> ConversationResolution:

        message = message.strip()

        if not message:
            raise ValueError(
                "message cannot be empty."
            )

        context = (
            conversation_context
            or {}
        )

        # First turn: no context exists, so skip the
        # extra LLM call entirely.
        if not context:
            return ConversationResolution(
                relation="standalone",
                used_context=False,
                resolved_message=message,
                reference_summary=None,
            )

        timezone_name = (
            self.settings.default_timezone
        )

        local_now = datetime.now(
            ZoneInfo(
                timezone_name
            )
        )

        payload = {
            "current_user_message":
                message,

            "environment": {
                "timezone":
                    timezone_name,

                "local_now":
                    local_now.isoformat(
                        timespec="seconds"
                    ),

                "local_date":
                    local_now
                    .date()
                    .isoformat(),
            },

            "conversation_context":
                context,
        }

        user_prompt = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        result = (
            self.grok
            .generate_structured(
                system_prompt=(
                    self.system_prompt
                ),
                user_prompt=user_prompt,
                response_model=(
                    ConversationResolution
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
                    "mizan-conversation-reasoner-v1"
                ),
            )
        )

        resolution = result.data

        resolved_message = (
            resolution
            .resolved_message
            .strip()
        )

        if not resolved_message:
            raise RuntimeError(
                "Conversation Reasoner returned "
                "an empty resolved_message."
            )

        # Return a clean immutable-by-convention model
        # rather than mutating the parsed object.
        return ConversationResolution(
            relation=resolution.relation,
            used_context=(
                resolution.used_context
            ),
            resolved_message=(
                resolved_message
            ),
            reference_summary=(
                resolution.reference_summary
            ),
        )
