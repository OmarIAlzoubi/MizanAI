from dataclasses import dataclass

from app.recipes.matcher import (
    normalize_recipe_text,
    recipe_similarity,
)

from app.recipes.repository import (
    RecipeRepository,
)


@dataclass(frozen=True)
class RecipeRouteMatch:

    recipe_id: str

    recipe_name: str

    score: float


class RecipeRouter:

    MATCH_THRESHOLD = 0.78

    AMBIGUITY_MARGIN = 0.06

    def __init__(
        self,
        repository:
            RecipeRepository | None = None,
    ):

        self.repository = (
            repository
            or RecipeRepository()
        )

    def match(
        self,
        message: str,
    ) -> RecipeRouteMatch | None:

        normalized_message = (
            normalize_recipe_text(
                message
            )
        )

        if not normalized_message:
            return None

        recipes = (
            self.repository
            .list_active()
        )

        if not recipes:
            return None

        scored: list[
            tuple[
                float,
                dict,
            ]
        ] = []

        for recipe in recipes:

            best_score = 0.0

            for example in (
                recipe["examples"]
            ):

                normalized_example = (
                    example[
                        "normalized"
                    ]
                )

                score = (
                    recipe_similarity(
                        normalized_message,
                        normalized_example,
                    )
                )

                best_score = max(
                    best_score,
                    score,
                )

            scored.append(
                (
                    best_score,
                    recipe,
                )
            )

        scored.sort(
            key=lambda item:
                item[0],
            reverse=True,
        )

        best_score, best_recipe = (
            scored[0]
        )

        if (
            best_score
            < self.MATCH_THRESHOLD
        ):

            return None

        if len(scored) > 1:

            second_score = (
                scored[1][0]
            )

            if (
                best_score
                - second_score
                < self.AMBIGUITY_MARGIN
            ):

                return None

        return RecipeRouteMatch(
            recipe_id=(
                best_recipe["id"]
            ),

            recipe_name=(
                best_recipe["name"]
            ),

            score=round(
                best_score,
                4,
            ),
        )