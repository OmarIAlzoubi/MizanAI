import os

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str

    xai_api_key: str | None
    xai_base_url: str
    xai_timeout_seconds: float
    xai_max_output_tokens: int

    # Fast / cheap model
    xai_understanding_model: str
    xai_understanding_reasoning: str

    # Stronger model
    xai_complex_model: str
    xai_complex_reasoning: str

    default_currency: str
    default_timezone: str
    default_week_start: int

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    def require_xai_api_key(self) -> str:
        if not self.xai_api_key:
            raise RuntimeError(
                "XAI_API_KEY is missing. "
                "Add it to the .env file."
            )

        return self.xai_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:

    # ---------------------------------
    # WEEK START
    # ---------------------------------

    week_start = int(
        os.getenv(
            "DEFAULT_WEEK_START",
            "6",
        )
    )

    if week_start not in range(7):
        raise ValueError(
            "DEFAULT_WEEK_START must be between 0 and 6."
        )

    # ---------------------------------
    # UNDERSTANDING MODEL REASONING
    # ---------------------------------

    understanding_reasoning = os.getenv(
        "XAI_UNDERSTANDING_REASONING",
        "none",
    ).lower()

    if understanding_reasoning not in {
        "none",
        "low",
        "medium",
        "high",
        "xhigh",
    }:
        raise ValueError(
            "XAI_UNDERSTANDING_REASONING must be "
            "none, low, medium, high, or xhigh."
        )

    # ---------------------------------
    # COMPLEX MODEL REASONING
    # ---------------------------------

    complex_reasoning = os.getenv(
        "XAI_COMPLEX_REASONING",
        "low",
    ).lower()

    if complex_reasoning not in {
        "none",
        "low",
        "medium",
        "high",
        "xhigh",
    }:
        raise ValueError(
            "XAI_COMPLEX_REASONING must be "
            "none, low, medium, high, or xhigh."
        )

    # ---------------------------------
    # SETTINGS
    # ---------------------------------

    return Settings(

        # App
        app_name=os.getenv(
            "APP_NAME",
            "MizanAI",
        ),

        app_env=os.getenv(
            "APP_ENV",
            "development",
        ),

        # xAI
        xai_api_key=os.getenv(
            "XAI_API_KEY"
        ),

        xai_base_url=os.getenv(
            "XAI_BASE_URL",
            "https://api.x.ai/v1",
        ),

        xai_timeout_seconds=float(
            os.getenv(
                "XAI_TIMEOUT_SECONDS",
                "60",
            )
        ),

        xai_max_output_tokens=int(
            os.getenv(
                "XAI_MAX_OUTPUT_TOKENS",
                "1600",
            )
        ),

        # Understanding model
        xai_understanding_model=os.getenv(
            "XAI_UNDERSTANDING_MODEL",
            "grok-4.3",
        ),

        xai_understanding_reasoning=(
            understanding_reasoning
        ),

        # Complex model
        xai_complex_model=os.getenv(
            "XAI_COMPLEX_MODEL",
            "grok-4.6",
        ),

        xai_complex_reasoning=(
            complex_reasoning
        ),

        # Defaults
        default_currency=os.getenv(
            "DEFAULT_CURRENCY",
            "SAR",
        ).upper(),

        default_timezone=os.getenv(
            "DEFAULT_TIMEZONE",
            "Asia/Riyadh",
        ),

        default_week_start=week_start,
    )