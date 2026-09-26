import json
import re

from dataclasses import (
    dataclass,
)

from pathlib import Path

from app.ai.grok_client import (
    GrokClient,
)

from app.contracts.recipe_compiler import (
    CompiledRecipe,
    RecipeCompilationDecision,
)

from app.core.config import (
    get_settings,
)

from app.recipes.learning_repository import (
    LearningRunRepository,
)

from app.recipes.matcher import (
    normalize_recipe_text,
    recipe_similarity,
)

from app.recipes.repository import (
    RecipeRepository,
)


PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "ai"
    / "prompts"
    / "recipe_compiler.txt"
)


@dataclass(frozen=True)
class RecipeCompileOutcome:

    status: str

    run_id: str

    recipe_id: str | None

    recipe_name: str | None

    recipe_status: str | None

    reason: str


class RecipeCompiler:

    EXISTING_MATCH_THRESHOLD = 0.86

    EXISTING_MATCH_MARGIN = 0.06

    PROMOTE_AFTER_POSITIVE = 2

    PROMOTE_AFTER_SUCCESS = 2

    def __init__(
        self,
        grok_client: GrokClient | None = None,
        learning_repository:
            LearningRunRepository | None = None,
        recipe_repository:
            RecipeRepository | None = None,
    ):

        self.grok = (
            grok_client
            or GrokClient()
        )

        self.learning_repository = (
            learning_repository
            or LearningRunRepository()
        )

        self.recipe_repository = (
            recipe_repository
            or RecipeRepository()
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

        # Recipe compilation is a structured
        # transformation task.
        #
        # Use the normal understanding model rather
        # than the expensive exploratory model.
        self.model = (
            self.settings
            .xai_understanding_model
        )

        self.reasoning_effort = (
            self.settings
            .xai_understanding_reasoning
        )

    # =====================================================
    # COMPILE
    # =====================================================

    def compile_run(
        self,
        run_id: str,
    ) -> RecipeCompileOutcome:

        run = (
            self.learning_repository
            .get(
                run_id
            )
        )

        # ---------------------------------------------
        # IDEMPOTENCY
        # ---------------------------------------------

        if run["recipe_id"]:

            recipe = (
                self.recipe_repository
                .get(
                    run[
                        "recipe_id"
                    ]
                )
            )

            return RecipeCompileOutcome(
                status=(
                    "already_compiled"
                ),

                run_id=run_id,

                recipe_id=(
                    run[
                        "recipe_id"
                    ]
                ),

                recipe_name=(
                    recipe["name"]
                    if recipe
                    else None
                ),

                recipe_status=(
                    recipe["status"]
                    if recipe
                    else None
                ),

                reason=(
                    "This learning run is already "
                    "attached to a recipe."
                ),
            )

        # ---------------------------------------------
        # MUST HAVE POSITIVE USER FEEDBACK
        # ---------------------------------------------

        if (
            run["feedback"]
            != "positive"
        ):

            return RecipeCompileOutcome(
                status="not_eligible",
                run_id=run_id,
                recipe_id=None,
                recipe_name=None,
                recipe_status=None,
                reason=(
                    "Only positively rated "
                    "Financial Agent runs are "
                    "eligible for recipe learning."
                ),
            )

        execution = (
            run["execution"]
        )

        if (
            execution.get("status")
            != "completed"
        ):

            return RecipeCompileOutcome(
                status="not_eligible",
                run_id=run_id,
                recipe_id=None,
                recipe_name=None,
                recipe_status=None,
                reason=(
                    "The Financial Agent execution "
                    "was not completed."
                ),
            )

        all_steps = (
            execution.get(
                "steps",
                [],
            )
        )

        successful_steps = [
            step
            for step
            in all_steps
            if (
                step.get("status")
                == "ok"
            )
        ]

        if not successful_steps:

            return RecipeCompileOutcome(
                status="not_eligible",
                run_id=run_id,
                recipe_id=None,
                recipe_name=None,
                recipe_status=None,
                reason=(
                    "No successful analytical "
                    "steps were available."
                ),
            )

        # V1 safety:
        # Do not learn from runs containing an
        # incomplete successful result set.
        if any(
            step.get(
                "truncated",
                False,
            )
            for step
            in successful_steps
        ):

            return RecipeCompileOutcome(
                status="not_eligible",
                run_id=run_id,
                recipe_id=None,
                recipe_name=None,
                recipe_status=None,
                reason=(
                    "The run contains truncated "
                    "analytical evidence."
                ),
            )

        # ---------------------------------------------
        # BUILD COMPILER INPUT
        # ---------------------------------------------

        payload = {
            "user_message":
                run["user_message"],

            "agent_task":
                run["agent_task"],

            "answer":
                run["answer"],

            "successful_steps":
                successful_steps,
        }

        raw_result = (
            self.grok
            .generate_structured(
                system_prompt=(
                    self.system_prompt
                ),

                user_prompt=json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),

                response_model=(
                    RecipeCompilationDecision
                ),

                model=(
                    self.model
                ),

                reasoning_effort=(
                    self.reasoning_effort
                ),

                prompt_cache_key=(
                    "mizan-recipe-compiler-v1"
                ),
            )
        )

        decision = (
            raw_result.data
        )

        if (
            not decision.reusable
        ):

            return RecipeCompileOutcome(
                status="not_reusable",
                run_id=run_id,
                recipe_id=None,
                recipe_name=None,
                recipe_status=None,
                reason=(
                    decision.reason
                ),
            )

        recipe = (
            decision.recipe
        )

        if recipe is None:

            raise RuntimeError(
                "Recipe Compiler returned "
                "reusable=true without recipe."
            )

        # ---------------------------------------------
        # PROGRAMMATIC SAFETY VALIDATION
        # ---------------------------------------------

        self._validate_compiled_recipe(
            recipe
        )

        examples = (
            self._prepare_examples(
                original_message=(
                    run[
                        "user_message"
                    ]
                ),

                generated_examples=(
                    recipe
                    .trigger_examples
                ),
            )
        )

        # ---------------------------------------------
        # CHECK FOR AN EXISTING RECIPE
        # ---------------------------------------------

        existing = (
            self._find_existing_recipe(
                examples
            )
        )

        if existing is not None:

            recipe_id = (
                existing["id"]
            )

            self.recipe_repository.add_examples(
                recipe_id=recipe_id,
                examples=examples,
                normalize=(
                    normalize_recipe_text
                ),
            )

            #self.recipe_repository.record_positive_feedback(
                #recipe_id
            #)

            #self.recipe_repository.record_success(
                #recipe_id
            #)

            current = (
                self.recipe_repository
                .get(
                    recipe_id
                )
            )

            if (
                current is not None
                and current["status"]
                == "candidate"
                and current[
                    "positive_feedback"
                ]
                >= self.PROMOTE_AFTER_POSITIVE
                and current[
                    "success_count"
                ]
                >= self.PROMOTE_AFTER_SUCCESS
            ):

                self.recipe_repository.promote(
                    recipe_id
                )

                current = (
                    self.recipe_repository
                    .get(
                        recipe_id
                    )
                )

            self.learning_repository.attach_recipe(
                run_id=run_id,
                recipe_id=recipe_id,
            )

            return RecipeCompileOutcome(
                status=(
                    "reinforced_existing"
                ),

                run_id=run_id,

                recipe_id=recipe_id,

                recipe_name=(
                    existing[
                        "name"
                    ]
                ),

                recipe_status=(
                    current["status"]
                    if current
                    else existing[
                        "status"
                    ]
                ),

                reason=(
                    "The successful run matched "
                    "an existing recipe and "
                    "reinforced it."
                ),
            )

        # ---------------------------------------------
        # CREATE NEW CANDIDATE
        # ---------------------------------------------

        recipe_name = (
            self._make_unique_name(
                recipe.name
            )
        )

        recipe_dict = (
            recipe.model_dump(
                mode="json"
            )
        )

        # Keep the final stored name aligned
        # with any collision-safe rename.
        recipe_dict[
            "name"
        ] = recipe_name

        recipe_id = (
            self.recipe_repository
            .create_candidate(
                name=recipe_name,

                objective=(
                    recipe.objective
                ),

                recipe=(
                    recipe_dict
                ),

                examples=(
                    examples
                ),

                normalize=(
                    normalize_recipe_text
                ),
            )
        )

        #self.recipe_repository.record_positive_feedback(
            #recipe_id
        #)

        #self.recipe_repository.record_success(
            #recipe_id
        #)

        self.learning_repository.attach_recipe(
            run_id=run_id,
            recipe_id=recipe_id,
        )

        return RecipeCompileOutcome(
            status="created_candidate",

            run_id=run_id,

            recipe_id=recipe_id,

            recipe_name=recipe_name,

            recipe_status="candidate",

            reason=(
                decision.reason
            ),
        )

    # =====================================================
    # VALIDATION
    # =====================================================

    def _validate_compiled_recipe(
        self,
        recipe: CompiledRecipe,
    ) -> None:

        serialized = json.dumps(
            recipe.model_dump(
                mode="json"
            ),
            ensure_ascii=False,
        )

        # Never persist concrete historical
        # YYYY-MM-DD dates inside a learned recipe.
        if re.search(
            r"\b20\d{2}-\d{2}-\d{2}\b",
            serialized,
        ):

            raise ValueError(
                "Compiled recipe contains "
                "a concrete historical date."
            )

        # Current/recent analytical recipes should
        # explicitly verify coverage.
        #
        # The compiler prompt is responsible for
        # adding this operation when appropriate.
        target_period_names = {
            parameter.name
            for parameter
            in recipe.parameters
            if parameter.kind
            == "period"
        }

        if target_period_names:

            operations = {
                step.operation
                for step
                in recipe.steps
            }

            comparison_operations = {
                "compare_spending_periods",
                "rank_dimension_delta",
                "reconcile_dimension_delta",
            }

            if (
                operations
                & comparison_operations
                and "verify_data_coverage"
                not in operations
            ):

                raise ValueError(
                    "Comparative period recipe "
                    "must verify data coverage."
                )

    # =====================================================
    # EXAMPLES
    # =====================================================

    @staticmethod
    def _prepare_examples(
        *,
        original_message: str,
        generated_examples: list[str],
    ) -> list[str]:

        output = []

        seen = set()

        for text in [
            original_message,
            *generated_examples,
        ]:

            text = (
                text.strip()
            )

            if not text:
                continue

            normalized = (
                normalize_recipe_text(
                    text
                )
            )

            if (
                not normalized
                or normalized in seen
            ):

                continue

            seen.add(
                normalized
            )

            output.append(
                text
            )

        return output

    # =====================================================
    # EXISTING RECIPE MATCH
    # =====================================================

    def _find_existing_recipe(
        self,
        examples: list[str],
    ) -> dict | None:

        recipes = (
            self.recipe_repository
            .list_matchable()
        )

        if not recipes:
            return None

        normalized_examples = [
            normalize_recipe_text(
                example
            )
            for example
            in examples
        ]

        scored = []

        for recipe in recipes:

            best = 0.0

            for query_example in (
                normalized_examples
            ):

                if not query_example:
                    continue

                for stored_example in (
                    recipe[
                        "examples"
                    ]
                ):

                    score = (
                        recipe_similarity(
                            query_example,
                            stored_example[
                                "normalized"
                            ],
                        )
                    )

                    best = max(
                        best,
                        score,
                    )

            scored.append(
                (
                    best,
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
            < self.EXISTING_MATCH_THRESHOLD
        ):

            return None

        if len(scored) > 1:

            second_score = (
                scored[1][0]
            )

            if (
                best_score
                - second_score
                < self.EXISTING_MATCH_MARGIN
            ):

                # Ambiguous recipe identity.
                # Better to avoid reinforcing the
                # wrong recipe.
                return None

        return best_recipe

    # =====================================================
    # UNIQUE NAME
    # =====================================================

    def _make_unique_name(
        self,
        name: str,
    ) -> str:

        if (
            self.recipe_repository
            .get_by_name(
                name
            )
            is None
        ):

            return name

        for index in range(
            2,
            100,
        ):

            candidate = (
                f"{name}_{index}"
            )

            if (
                self.recipe_repository
                .get_by_name(
                    candidate
                )
                is None
            ):

                return candidate

        raise RuntimeError(
            "Unable to generate "
            "a unique recipe name."
        )