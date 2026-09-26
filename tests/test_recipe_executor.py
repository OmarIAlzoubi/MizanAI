import json

from app.infrastructure.database.schema import (
    initialize_database,
)

from app.recipes.executor import (
    RecipeExecutor,
)


def main():

    initialize_database()

    executor = (
        RecipeExecutor()
    )

    result = (
        executor.execute_by_name(
            recipe_name=(
                "explain_spending_change"
            ),

            user_message=(
                "ليش صرفي مرتفع هذا الشهر؟"
            ),
        )
    )

    print(
        "\n[Recipe Execution Result]"
    )

    print(
        json.dumps(
            result.model_dump(
                mode="json"
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":

    main()