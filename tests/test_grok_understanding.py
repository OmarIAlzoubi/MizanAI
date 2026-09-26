from app.ai.understanding import (
    UnderstandingService,
)


def main():
    understanding = UnderstandingService()

    message = (
        "دفعت 300 ريال في إحسان أمس"
    )

    print("\nUSER")
    print(message)

    result = understanding.understand(
        message=message
    )

    print("\nACTION PLAN")
    print(
        result.data.model_dump_json(
            indent=2
        )
    )

    print("\nLLM USAGE")
    print(
        "Model:",
        result.model,
    )

    print(
        "Input tokens:",
        result.usage.input_tokens,
    )

    print(
        "Output tokens:",
        result.usage.output_tokens,
    )

    print(
        "Total tokens:",
        result.usage.total_tokens,
    )
    print(
        "Cached input tokens:",
        result.usage.cached_input_tokens,
    )

    print(
        "Reasoning tokens:",
        result.usage.reasoning_tokens,
    )

    print(
        "Cost ticks:",
        result.usage.cost_in_usd_ticks,
    )

    


if __name__ == "__main__":
    main()