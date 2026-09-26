import json

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)


class RecipeRepository:

    ALLOWED_STATUSES = {
        "candidate",
        "active",
        "disabled",
    }

    def __init__(
        self,
        database: Database | None = None,
    ):

        self.database = (
            database
            or get_default_database()
        )

    # =====================================================
    # CREATE
    # =====================================================

    def create_candidate(
        self,
        *,
        name: str,
        objective: str,
        recipe: dict,
        examples: list[str],
        normalize,
    ) -> str:

        recipe_id = str(
            uuid4()
        )

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        with self.database.session() as conn:

            conn.execute(
                """
                INSERT INTO analysis_recipes (
                    id,
                    name,
                    objective,
                    status,
                    recipe_json,
                    created_at_utc,
                    updated_at_utc
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    name,
                    objective,
                    "candidate",
                    json.dumps(
                        recipe,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    now,
                    now,
                ),
            )

            self._insert_examples(
                conn=conn,
                recipe_id=recipe_id,
                examples=examples,
                normalize=normalize,
                now=now,
            )

        return recipe_id

    # =====================================================
    # EXAMPLES
    # =====================================================

    def add_examples(
        self,
        *,
        recipe_id: str,
        examples: list[str],
        normalize,
    ) -> None:

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        with self.database.session() as conn:

            self._insert_examples(
                conn=conn,
                recipe_id=recipe_id,
                examples=examples,
                normalize=normalize,
                now=now,
            )

            conn.execute(
                """
                UPDATE analysis_recipes
                SET updated_at_utc = ?
                WHERE id = ?
                """,
                (
                    now,
                    recipe_id,
                ),
            )

    def _insert_examples(
        self,
        *,
        conn,
        recipe_id: str,
        examples: list[str],
        normalize,
        now: str,
    ) -> None:

        for example in examples:

            example = (
                example.strip()
            )

            if not example:
                continue

            normalized = (
                normalize(
                    example
                )
            )

            if not normalized:
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO
                analysis_recipe_examples (
                    recipe_id,
                    example_text,
                    normalized_text,
                    created_at_utc
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    example,
                    normalized,
                    now,
                ),
            )

    # =====================================================
    # GET
    # =====================================================

    def get(
        self,
        recipe_id: str,
    ) -> dict | None:

        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT
                    id,
                    name,
                    objective,
                    status,
                    recipe_json,
                    positive_feedback,
                    negative_feedback,
                    success_count,
                    failure_count,
                    created_at_utc,
                    updated_at_utc,
                    last_used_at_utc
                FROM analysis_recipes
                WHERE id = ?
                """,
                (
                    recipe_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return {
            "id":
                row["id"],

            "name":
                row["name"],

            "objective":
                row["objective"],

            "status":
                row["status"],

            "recipe":
                json.loads(
                    row["recipe_json"]
                ),

            "positive_feedback":
                row["positive_feedback"],

            "negative_feedback":
                row["negative_feedback"],

            "success_count":
                row["success_count"],

            "failure_count":
                row["failure_count"],

            "created_at_utc":
                row["created_at_utc"],

            "updated_at_utc":
                row["updated_at_utc"],

            "last_used_at_utc":
                row["last_used_at_utc"],
        }

    def get_by_name(
        self,
        name: str,
    ) -> dict | None:

        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT id
                FROM analysis_recipes
                WHERE name = ?
                """,
                (
                    name,
                ),
            ).fetchone()

        if row is None:
            return None

        return self.get(
            row["id"]
        )

    # =====================================================
    # LIST FOR MATCHING
    # =====================================================

    def list_matchable(
        self,
        statuses: tuple[
            str,
            ...
        ] = (
            "candidate",
            "active",
        ),
    ) -> list[dict]:

        if not statuses:
            return []

        for status in statuses:

            if (
                status
                not in self.ALLOWED_STATUSES
            ):

                raise ValueError(
                    "Invalid recipe status."
                )

        placeholders = ",".join(
            "?"
            for _ in statuses
        )

        with self.database.session() as conn:

            rows = conn.execute(
                f"""
                SELECT
                    r.id,
                    r.name,
                    r.objective,
                    r.status,
                    r.recipe_json,
                    r.positive_feedback,
                    r.negative_feedback,
                    r.success_count,
                    r.failure_count,
                    e.example_text,
                    e.normalized_text
                FROM analysis_recipes r

                JOIN analysis_recipe_examples e
                    ON e.recipe_id = r.id

                WHERE r.status IN (
                    {placeholders}
                )

                ORDER BY
                    r.id,
                    e.id
                """,
                statuses,
            ).fetchall()

        recipes: dict[
            str,
            dict,
        ] = {}

        for row in rows:

            recipe_id = (
                row["id"]
            )

            if (
                recipe_id
                not in recipes
            ):

                recipes[
                    recipe_id
                ] = {
                    "id":
                        recipe_id,

                    "name":
                        row["name"],

                    "objective":
                        row["objective"],

                    "status":
                        row["status"],

                    "recipe":
                        json.loads(
                            row[
                                "recipe_json"
                            ]
                        ),

                    "positive_feedback":
                        row[
                            "positive_feedback"
                        ],

                    "negative_feedback":
                        row[
                            "negative_feedback"
                        ],

                    "success_count":
                        row[
                            "success_count"
                        ],

                    "failure_count":
                        row[
                            "failure_count"
                        ],

                    "examples": [],
                }

            recipes[
                recipe_id
            ]["examples"].append(
                {
                    "text":
                        row[
                            "example_text"
                        ],

                    "normalized":
                        row[
                            "normalized_text"
                        ],
                }
            )

        return list(
            recipes.values()
        )

    def list_active(
        self,
    ) -> list[dict]:

        return self.list_matchable(
            statuses=(
                "active",
            )
        )

    # =====================================================
    # PROMOTE
    # =====================================================

    def promote(
        self,
        recipe_id: str,
    ) -> None:

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        with self.database.session() as conn:

            conn.execute(
                """
                UPDATE analysis_recipes
                SET
                    status = 'active',
                    updated_at_utc = ?
                WHERE id = ?
                """,
                (
                    now,
                    recipe_id,
                ),
            )

    # =====================================================
    # FEEDBACK / PERFORMANCE
    # =====================================================

    def record_positive_feedback(
        self,
        recipe_id: str,
    ) -> None:

        self._increment(
            recipe_id=recipe_id,
            column="positive_feedback",
        )

    def record_negative_feedback(
        self,
        recipe_id: str,
    ) -> None:

        self._increment(
            recipe_id=recipe_id,
            column="negative_feedback",
        )

    def record_success(
        self,
        recipe_id: str,
    ) -> None:

        self._increment(
            recipe_id=recipe_id,
            column="success_count",
        )

    def record_failure(
        self,
        recipe_id: str,
    ) -> None:

        self._increment(
            recipe_id=recipe_id,
            column="failure_count",
        )

    def _increment(
        self,
        *,
        recipe_id: str,
        column: str,
    ) -> None:

        allowed = {
            "positive_feedback",
            "negative_feedback",
            "success_count",
            "failure_count",
        }

        if column not in allowed:

            raise ValueError(
                "Invalid recipe counter."
            )

        now = (
            datetime.now(
                timezone.utc
            )
            .isoformat()
        )

        with self.database.session() as conn:

            conn.execute(
                f"""
                UPDATE analysis_recipes
                SET
                    {column} = {column} + 1,
                    updated_at_utc = ?
                WHERE id = ?
                """,
                (
                    now,
                    recipe_id,
                ),
            )