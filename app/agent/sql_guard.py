import re


class UnsafeFinancialQueryError(
    ValueError
):
    pass


class FinancialSQLGuard:

    ALLOWED_VIEWS = {
        "v_financial_transactions",
        "v_financial_concepts",
        "v_financial_snapshot",
    }

    FORBIDDEN_OBJECTS = {
        "transactions",
        "semantic_annotations",
        "annotation_concepts",
        "app_state",
        "accounts",

        "sqlite_master",
        "sqlite_schema",
        "sqlite_temp_master",
        "sqlite_temp_schema",
    }

    FORBIDDEN_KEYWORDS = {
        "insert",
        "update",
        "delete",
        "replace",

        "create",
        "drop",
        "alter",

        "attach",
        "detach",

        "pragma",

        "vacuum",
        "reindex",

        "begin",
        "commit",
        "rollback",

        "savepoint",
        "release",

        "trigger",

        "load_extension",
        "readfile",
        "writefile",
    }

    COMMENT_MARKERS = (
        "--",
        "/*",
        "*/",
    )

    @classmethod
    def validate(
        cls,
        sql: str,
    ) -> str:

        if not sql:
            raise UnsafeFinancialQueryError(
                "SQL query is empty."
            )

        sql = sql.strip()

        if not sql:
            raise UnsafeFinancialQueryError(
                "SQL query is empty."
            )

        lowered = sql.lower()

        # =============================================
        # NO COMMENTS
        # =============================================

        for marker in cls.COMMENT_MARKERS:

            if marker in lowered:

                raise UnsafeFinancialQueryError(
                    "SQL comments are not allowed."
                )

        # =============================================
        # SINGLE STATEMENT ONLY
        # =============================================

        cleaned = sql.rstrip()

        if cleaned.endswith(";"):
            cleaned = (
                cleaned[:-1]
                .rstrip()
            )

        if ";" in cleaned:

            raise UnsafeFinancialQueryError(
                "Multiple SQL statements "
                "are not allowed."
            )

        lowered = cleaned.lower()

        # =============================================
        # SELECT / WITH ONLY
        # =============================================

        first_word_match = re.match(
            r"^\s*([a-zA-Z]+)",
            cleaned,
        )

        if not first_word_match:

            raise UnsafeFinancialQueryError(
                "Unable to determine "
                "SQL query type."
            )

        first_word = (
            first_word_match
            .group(1)
            .lower()
        )

        if first_word not in {
            "select",
            "with",
        }:

            raise UnsafeFinancialQueryError(
                "Only read-only SELECT "
                "queries are allowed."
            )

        # =============================================
        # FORBIDDEN OPERATIONS
        # =============================================

        words = set(
            re.findall(
                r"\b[a-zA-Z_]+\b",
                lowered,
            )
        )

        blocked = (
            words
            & cls.FORBIDDEN_KEYWORDS
        )

        if blocked:

            raise UnsafeFinancialQueryError(
                "Forbidden SQL operation: "
                + ", ".join(
                    sorted(blocked)
                )
            )

        # =============================================
        # INTERNAL STORAGE MUST NEVER BE QUERIED
        # =============================================

        for object_name in (
            cls.FORBIDDEN_OBJECTS
        ):

            if re.search(
                r"\b"
                + re.escape(
                    object_name
                )
                + r"\b",
                lowered,
            ):

                raise UnsafeFinancialQueryError(
                    "Direct access to "
                    f"'{object_name}' "
                    "is not allowed."
                )

        # =============================================
        # BLOCK SQLITE INTERNAL OBJECTS
        # =============================================

        if "sqlite_" in lowered:

            raise UnsafeFinancialQueryError(
                "SQLite internal objects "
                "are not allowed."
            )

        # =============================================
        # QUERY MUST USE AT LEAST ONE SAFE VIEW
        # =============================================

        uses_allowed_view = any(
            re.search(
                r"\b"
                + re.escape(view)
                + r"\b",
                lowered,
            )
            is not None

            for view
            in cls.ALLOWED_VIEWS
        )

        if not uses_allowed_view:

            raise UnsafeFinancialQueryError(
                "Query must use an approved "
                "financial analytical view."
            )

        return cleaned