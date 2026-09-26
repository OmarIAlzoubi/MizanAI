from app.infrastructure.database.schema import (
    initialize_database,
)

from app.recipes.matcher import (
    RecipeMatcher,
    normalize_recipe_text,
)

from app.recipes.repository import (
    RecipeRepository,
)


def main():

    initialize_database()

    repo = RecipeRepository()

    with repo.database.session() as conn:

        conn.execute(
            """
            DELETE FROM analysis_recipes
            WHERE name = ?
            """,
            (
                "explain_spending_change",
            ),
        )

    recipe_id = (
        repo.create_candidate(

            name=(
                "explain_spending_change"
            ),

            objective=(
                "Explain the main contributors "
                "to a change in spending between "
                "comparable periods."
            ),

            recipe={
                "version": "1.0",

                "type":
                    "financial_analysis",

                "steps": [
                    "compare_spending_totals",
                    "calculate_merchant_deltas",
                    "calculate_concept_deltas",
                    "reconcile_change",
                ],
            },

            examples=[
                "ليش صرفي مرتفع هذا الشهر؟",
                "وش سبب زيادة مصاريفي هذا الشهر؟",
                "ليش مصاريفي زادت هالأسبوع؟",
                "ايش اللي رفع صرفي الفترة هذي؟",
                "Why is my spending higher this month?",
            ],

            normalize=(
                normalize_recipe_text
            ),
        )
    )

    repo.promote(
        recipe_id
    )

    matcher = (
        RecipeMatcher()
    )

    tests = [

        "ليش صرفي مرتفع هذا الشهر؟",

        "وش سبب زيادة مصاريفي هالأسبوع؟",

        "ليش انفاقي ارتفع الشهر الحالي؟",

        "ايش اللي رفع مصاريفي؟",

        # المفروض ما يطابق
        "كم رصيدي؟",

        # المفروض ما يطابق
        "كم صرفت على القهوة؟",
    ]

    for text in tests:

        print(
            "\nQUERY:",
            text,
        )

        print(
            "NORMALIZED:",
            normalize_recipe_text(
                text
            ),
        )

        match = (
            matcher.match(
                text
            )
        )

        if match is None:

            print(
                "MATCH: NONE"
            )

        else:

            print(
                "MATCH:",
                match.name,
            )

            print(
                "SCORE:",
                match.score,
            )

            print(
                "EXAMPLE:",
                match.matched_example,
            )


if __name__ == "__main__":

    main()