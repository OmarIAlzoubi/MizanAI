from statistics import mean
from time import sleep

from app.ai.understanding import (
    UnderstandingService,
)


MESSAGES = [
    "دفعت 300 ريال في إحسان أمس",
    "كم تبرعت هذا الشهر؟",
] * 5


def percentile(
    values: list[float],
    percent: float,
) -> float:

    ordered = sorted(values)

    index = int(
        (len(ordered) - 1)
        * percent
    )

    return ordered[index]


def main():

    understanding = (
        UnderstandingService()
    )

    latencies = []

    print(
        "\n=============================="
    )
    print(
        "MIZAN UNDERSTANDING BENCHMARK"
    )
    print(
        "=============================="
    )

    for index, message in enumerate(
        MESSAGES,
        start=1,
    ):

        result = (
            understanding.understand(
                message=message
            )
        )

        latency = (
            result.latency_ms
        )

        latencies.append(
            latency
        )

        usage = result.usage

        print(
            f"\n[{index:02d}] "
            f"{latency:.0f} ms"
        )

        print(
            f"Message: {message}"
        )

        print(
            f"Model: {result.model}"
        )

        print(
            "Input:",
            usage.input_tokens,
        )

        print(
            "Cached:",
            usage.cached_input_tokens,
        )

        print(
            "Output:",
            usage.output_tokens,
        )

        print(
            "Reasoning:",
            usage.reasoning_tokens,
        )

        print(
            "Cost ticks:",
            usage.cost_in_usd_ticks,
        )

        # Small gap so we are not testing
        # burst behavior only.
        sleep(0.25)

    print(
        "\n=============================="
    )
    print(
        "RESULTS"
    )
    print(
        "=============================="
    )

    print(
        f"Requests: {len(latencies)}"
    )

    print(
        f"Min: {min(latencies):.0f} ms"
    )

    print(
        f"Average: {mean(latencies):.0f} ms"
    )

    print(
        "P50:",
        f"{percentile(latencies, 0.50):.0f} ms"
    )

    print(
        "P95:",
        f"{percentile(latencies, 0.95):.0f} ms"
    )

    print(
        f"Max: {max(latencies):.0f} ms"
    )


if __name__ == "__main__":
    main()