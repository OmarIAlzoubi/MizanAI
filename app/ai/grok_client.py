from dataclasses import dataclass
from typing import Generic, TypeVar
from time import perf_counter
from openai import OpenAI
from pydantic import BaseModel

from app.core.config import get_settings


T = TypeVar(
    "T",
    bound=BaseModel,
)


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None

    output_tokens: int | None = None
    reasoning_tokens: int | None = None

    total_tokens: int | None = None

    cost_in_usd_ticks: int | None = None


@dataclass(frozen=True)
class StructuredLLMResult(
    Generic[T]
):
    data: T
    usage: LLMUsage
    model: str
    latency_ms: float


class GrokClient:
    def __init__(self):
        self.settings = get_settings()

        api_key = (
            self.settings.require_xai_api_key()
        )

        self.client = OpenAI(
            api_key=api_key,
            base_url=self.settings.xai_base_url,
            timeout=self.settings.xai_timeout_seconds,
        )

    # =========================================================
    # STRUCTURED GENERATION
    # =========================================================

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        model: str,
        reasoning_effort: str,
        prompt_cache_key: str | None = None,
    ) -> StructuredLLMResult[T]:
        started_at = perf_counter()
        response = self.client.responses.parse(
            model=model,

            reasoning={
                "effort": reasoning_effort
            },

            max_output_tokens=(
                self.settings.xai_max_output_tokens
            ),

            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],

            text_format=response_model,

            extra_body=(
                {
                    "prompt_cache_key":
                        prompt_cache_key
                }
                if prompt_cache_key
                else {}
            ),
        )
        latency_ms = (
            perf_counter() - started_at
        ) * 1000
        parsed = response.output_parsed

        if parsed is None:
            raise RuntimeError(
                "Grok returned no parsed "
                "structured output."
            )

        # -----------------------------------------
        # USAGE
        # -----------------------------------------

        raw_usage = getattr(
            response,
            "usage",
            None,
        )

        input_details = getattr(
            raw_usage,
            "input_tokens_details",
            None,
        )

        output_details = getattr(
            raw_usage,
            "output_tokens_details",
            None,
        )

        usage = LLMUsage(
            input_tokens=getattr(
                raw_usage,
                "input_tokens",
                None,
            ),

            cached_input_tokens=getattr(
                input_details,
                "cached_tokens",
                None,
            ),

            output_tokens=getattr(
                raw_usage,
                "output_tokens",
                None,
            ),

            reasoning_tokens=getattr(
                output_details,
                "reasoning_tokens",
                None,
            ),

            total_tokens=getattr(
                raw_usage,
                "total_tokens",
                None,
            ),

            cost_in_usd_ticks=getattr(
                raw_usage,
                "cost_in_usd_ticks",
                None,
            ),
        )

        return StructuredLLMResult(
            data=parsed,
            usage=usage,
            model=model,
            latency_ms=latency_ms,
        )
    # =========================================================
    # NORMAL TEXT GENERATION
    # =========================================================

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        reasoning_effort: str,
        prompt_cache_key: str | None = None,
    ) -> str:

        response = self.client.responses.create(
            model=model,

            reasoning={
                "effort": reasoning_effort
            },

            max_output_tokens=(
                self.settings.xai_max_output_tokens
            ),

            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],

            extra_body=(
                {
                    "prompt_cache_key":
                        prompt_cache_key
                }
                if prompt_cache_key
                else {}
            ),
        )

        return response.output_text