def ensure_recipe_schema(
    conn,
) -> None:

    conn.executescript(
        """
        -- =================================================
        -- RECIPES
        -- =================================================

        CREATE TABLE IF NOT EXISTS analysis_recipes (
            id TEXT PRIMARY KEY,

            name TEXT NOT NULL UNIQUE,

            objective TEXT NOT NULL,

            status TEXT NOT NULL
                DEFAULT 'candidate'
                CHECK (
                    status IN (
                        'candidate',
                        'active',
                        'disabled'
                    )
                ),

            recipe_json TEXT NOT NULL,

            positive_feedback INTEGER
                NOT NULL DEFAULT 0,

            negative_feedback INTEGER
                NOT NULL DEFAULT 0,

            success_count INTEGER
                NOT NULL DEFAULT 0,

            failure_count INTEGER
                NOT NULL DEFAULT 0,

            created_at_utc TEXT NOT NULL,

            updated_at_utc TEXT NOT NULL,

            last_used_at_utc TEXT
        );


        -- =================================================
        -- RECIPE EXAMPLES
        -- =================================================

        CREATE TABLE IF NOT EXISTS analysis_recipe_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            recipe_id TEXT NOT NULL,

            example_text TEXT NOT NULL,

            normalized_text TEXT NOT NULL,

            created_at_utc TEXT NOT NULL,

            FOREIGN KEY (
                recipe_id
            )
            REFERENCES analysis_recipes(id)
            ON DELETE CASCADE,

            UNIQUE (
                recipe_id,
                normalized_text
            )
        );


        -- =================================================
        -- AGENT LEARNING RUNS
        --
        -- Every successful Financial Agent execution that
        -- may later teach the Recipe Layer is stored here.
        -- =================================================

        CREATE TABLE IF NOT EXISTS analysis_learning_runs (
            id TEXT PRIMARY KEY,

            source TEXT NOT NULL
                DEFAULT 'financial_agent'
                CHECK (
                    source = 'financial_agent'
                ),

            user_message TEXT NOT NULL,

            agent_task TEXT NOT NULL,

            route_confidence REAL,

            route_reason TEXT,

            answer TEXT NOT NULL,

            execution_json TEXT NOT NULL,

            feedback TEXT
                CHECK (
                    feedback IS NULL
                    OR feedback IN (
                        'positive',
                        'negative'
                    )
                ),

            recipe_id TEXT,

            created_at_utc TEXT NOT NULL,

            feedback_at_utc TEXT,

            FOREIGN KEY (
                recipe_id
            )
            REFERENCES analysis_recipes(id)
            ON DELETE SET NULL
        );


        -- =================================================
        -- INDEXES
        -- =================================================

        CREATE INDEX IF NOT EXISTS
        idx_analysis_recipes_status
        ON analysis_recipes(
            status
        );


        CREATE INDEX IF NOT EXISTS
        idx_recipe_examples_recipe
        ON analysis_recipe_examples(
            recipe_id
        );


        CREATE INDEX IF NOT EXISTS
        idx_learning_runs_feedback
        ON analysis_learning_runs(
            feedback
        );


        CREATE INDEX IF NOT EXISTS
        idx_learning_runs_recipe
        ON analysis_learning_runs(
            recipe_id
        );


        CREATE INDEX IF NOT EXISTS
        idx_learning_runs_created
        ON analysis_learning_runs(
            created_at_utc
        );
        """
    )