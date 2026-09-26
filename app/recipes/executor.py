from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from zoneinfo import ZoneInfo

from app.agent.finance_query_tool import (
    FinanceQueryTool,
)

from app.contracts.recipe_compiler import (
    CompiledRecipe,
    RecipeStep,
)

from app.contracts.recipe_execution import (
    RecipeExecutionResult,
    RecipeExecutionStep,
)

from app.core.config import (
    get_settings,
)

from app.recipes.period_resolver import (
    RecipeParameterResolutionError,
    RecipePeriodResolver,
    ResolvedPeriod,
)

from app.recipes.repository import (
    RecipeRepository,
)


class RecipeExecutionError(
    RuntimeError
):
    pass


class RecipeExecutor:

    def __init__(
        self,
        query_tool:
            FinanceQueryTool | None = None,

        recipe_repository:
            RecipeRepository | None = None,

        period_resolver:
            RecipePeriodResolver | None = None,
    ):

        self.query_tool = (
            query_tool
            or FinanceQueryTool(
                max_rows=100,
                timeout_seconds=2.0,
            )
        )

        self.recipe_repository = (
            recipe_repository
            or RecipeRepository()
        )

        self.period_resolver = (
            period_resolver
            or RecipePeriodResolver()
        )

        self.settings = (
            get_settings()
        )

        self.timezone = ZoneInfo(
            self.settings
            .default_timezone
        )

    # =====================================================
    # EXECUTE BY NAME
    # =====================================================

    def execute_by_name(
        self,
        *,
        recipe_name: str,
        user_message: str,
    ) -> RecipeExecutionResult:

        record = (
            self.recipe_repository
            .get_by_name(
                recipe_name
            )
        )

        if record is None:

            raise RecipeExecutionError(
                f"Recipe not found: "
                f"{recipe_name}"
            )

        return self.execute(
            recipe_record=record,
            user_message=user_message,
        )

    # =====================================================
    # EXECUTE
    # =====================================================

    def execute(
        self,
        *,
        recipe_record: dict,
        user_message: str,
    ) -> RecipeExecutionResult:

        user_message = (
            user_message.strip()
        )

        recipe_id = (
            recipe_record["id"]
        )

        recipe_name = (
            recipe_record["name"]
        )

        try:

            recipe = (
                CompiledRecipe
                .model_validate(
                    recipe_record[
                        "recipe"
                    ]
                )
            )

        except Exception as exc:

            return RecipeExecutionResult(
                status="failed",
                recipe_id=recipe_id,
                recipe_name=recipe_name,
                user_message=user_message,
                fallback_reason=(
                    "Stored recipe is invalid: "
                    f"{exc}"
                ),
            )

        # =============================================
        # PARAMETER RESOLUTION
        # =============================================

        try:

            target_period = (
                self.period_resolver
                .resolve_target_period(
                    message=user_message
                )
            )

        except (
            RecipeParameterResolutionError
        ) as exc:

            return RecipeExecutionResult(
                status="needs_fallback",
                recipe_id=recipe_id,
                recipe_name=recipe_name,
                user_message=user_message,
                fallback_reason=str(exc),
            )

        parameters: dict[
            str,
            object,
        ] = {
            "target_period":
                target_period.to_dict()
        }

        coverage_end: (
            str | None
        ) = None

        steps: list[
            RecipeExecutionStep
        ] = []

        # =============================================
        # EXECUTION LOOP
        # =============================================

        for recipe_step in (
            recipe.steps
        ):

            try:

                if (
                    recipe_step.operation
                    == "verify_data_coverage"
                ):

                    (
                        target_period,
                        coverage_end,
                        step,
                    ) = (
                        self._execute_coverage_step(
                            recipe_step,
                            target_period,
                        )
                    )

                    parameters[
                        "target_period"
                    ] = (
                        target_period
                        .to_dict()
                    )

                    # Derived parameters must use the
                    # EFFECTIVE covered target period.
                    self._resolve_derived_parameters(
                        recipe=recipe,
                        target_period=target_period,
                        parameters=parameters,
                    )

                else:

                    # Recipes without an explicit
                    # coverage step can still resolve
                    # derived periods from the target.
                    self._resolve_derived_parameters(
                        recipe=recipe,
                        target_period=target_period,
                        parameters=parameters,
                    )

                    step = (
                        self._execute_analytical_step(
                            recipe_step=recipe_step,
                            parameters=parameters,
                        )
                    )

                steps.append(
                    step
                )

                if (
                    step.status
                    != "ok"
                ):

                    return RecipeExecutionResult(
                        status="needs_fallback",
                        recipe_id=recipe_id,
                        recipe_name=recipe_name,
                        user_message=user_message,
                        parameters=parameters,
                        coverage_end_local_date=(
                            coverage_end
                        ),
                        steps=steps,
                        fallback_reason=(
                            step.error
                            or (
                                "Recipe step "
                                "execution failed."
                            )
                        ),
                    )

                if step.truncated:

                    return RecipeExecutionResult(
                        status="needs_fallback",
                        recipe_id=recipe_id,
                        recipe_name=recipe_name,
                        user_message=user_message,
                        parameters=parameters,
                        coverage_end_local_date=(
                            coverage_end
                        ),
                        steps=steps,
                        fallback_reason=(
                            "Recipe result was "
                            "truncated."
                        ),
                    )

            except Exception as exc:

                error_step = (
                    RecipeExecutionStep(
                        step_id=(
                            recipe_step
                            .step_id
                        ),

                        operation=(
                            recipe_step
                            .operation
                        ),

                        purpose=(
                            recipe_step
                            .purpose
                        ),

                        status="error",

                        error=(
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

                steps.append(
                    error_step
                )

                return RecipeExecutionResult(
                    status="needs_fallback",
                    recipe_id=recipe_id,
                    recipe_name=recipe_name,
                    user_message=user_message,
                    parameters=parameters,
                    coverage_end_local_date=(
                        coverage_end
                    ),
                    steps=steps,
                    fallback_reason=(
                        error_step.error
                    ),
                )

        # =============================================
        # SUCCESS
        # =============================================

        return RecipeExecutionResult(
            status="completed",
            recipe_id=recipe_id,
            recipe_name=recipe_name,
            user_message=user_message,
            parameters=parameters,
            coverage_end_local_date=(
                coverage_end
            ),
            steps=steps,
            fallback_reason=None,
        )

    # =====================================================
    # DERIVED PARAMETERS
    # =====================================================

    def _resolve_derived_parameters(
        self,
        *,
        recipe: CompiledRecipe,
        target_period: ResolvedPeriod,
        parameters: dict,
    ) -> None:

        for parameter in (
            recipe.parameters
        ):

            if (
                parameter.source
                != "derived"
            ):

                continue

            if (
                parameter.name
                in parameters
            ):

                # Recalculate comparison after coverage
                # clipping if needed.
                if (
                    parameter.kind
                    != "period"
                ):

                    continue

            if (
                parameter.kind
                != "period"
            ):

                raise RecipeExecutionError(
                    "Recipe Executor V1 supports "
                    "derived period parameters only."
                )

            if (
                parameter.derivation
                == (
                    "same_elapsed_previous_period"
                )
            ):

                resolved = (
                    self.period_resolver
                    .derive_same_elapsed_previous_period(
                        target=target_period
                    )
                )

            elif (
                parameter.derivation
                == "previous_period"
            ):

                resolved = (
                    self.period_resolver
                    .derive_same_elapsed_previous_period(
                        target=target_period
                    )
                )

            else:

                raise RecipeExecutionError(
                    "Unsupported period "
                    "derivation."
                )

            parameters[
                parameter.name
            ] = resolved.to_dict()

    # =====================================================
    # COVERAGE
    # =====================================================

    def _execute_coverage_step(
        self,
        recipe_step: RecipeStep,
        target_period: ResolvedPeriod,
    ) -> tuple[
        ResolvedPeriod,
        str,
        RecipeExecutionStep,
    ]:

        sql = """
        SELECT
            latest_transaction_utc
        FROM v_financial_snapshot
        """.strip()

        result = (
            self.query_tool
            .execute(
                sql
            )
        )

        if (
            not result.rows
            or result.rows[0].get(
                "latest_transaction_utc"
            ) is None
        ):

            raise RecipeExecutionError(
                "No transaction coverage "
                "information is available."
            )

        raw_timestamp = str(
            result.rows[0][
                "latest_transaction_utc"
            ]
        )

        coverage_datetime = (
            self._parse_utc_datetime(
                raw_timestamp
            )
        )

        coverage_local_date = (
            coverage_datetime
            .astimezone(
                self.timezone
            )
            .date()
        )

        effective_target = (
            self.period_resolver
            .apply_coverage(
                period=target_period,
                coverage_end=(
                    coverage_local_date
                ),
            )
        )

        rows = [
            {
                "latest_transaction_utc":
                    raw_timestamp,

                "coverage_end_local_date":
                    coverage_local_date
                    .isoformat(),

                "requested_start":
                    target_period
                    .requested_start
                    .isoformat(),

                "requested_end":
                    target_period
                    .requested_end
                    .isoformat(),

                "effective_start":
                    effective_target
                    .start
                    .isoformat(),

                "effective_end":
                    effective_target
                    .end
                    .isoformat(),

                "clipped":
                    effective_target
                    .clipped_by_coverage,
            }
        ]

        step = RecipeExecutionStep(
            step_id=(
                recipe_step.step_id
            ),

            operation=(
                recipe_step.operation
            ),

            purpose=(
                recipe_step.purpose
            ),

            status="ok",

            sql=sql,

            columns=list(
                rows[0].keys()
            ),

            rows=rows,

            row_count=1,

            truncated=False,

            error=None,
        )

        return (
            effective_target,
            coverage_local_date
            .isoformat(),
            step,
        )

    # =====================================================
    # ANALYTICAL OPERATIONS
    # =====================================================

    def _execute_analytical_step(
        self,
        *,
        recipe_step: RecipeStep,
        parameters: dict,
    ) -> RecipeExecutionStep:

        operation = (
            recipe_step.operation
        )

        if operation == "snapshot":

            sql = (
                self._build_snapshot_sql()
            )

        elif (
            operation
            == "aggregate_spending"
        ):

            target = (
                self._get_period(
                    parameters,
                    recipe_step
                    .target_period_param,
                )
            )

            sql = (
                self._build_aggregate_spending_sql(
                    target=target,
                    spending_only=(
                        recipe_step
                        .spending_only
                    ),
                )
            )

        elif (
            operation
            == "compare_spending_periods"
        ):

            target = (
                self._get_period(
                    parameters,
                    recipe_step
                    .target_period_param,
                )
            )

            comparison = (
                self._get_period(
                    parameters,
                    recipe_step
                    .comparison_period_param,
                )
            )

            sql = (
                self._build_compare_periods_sql(
                    target=target,
                    comparison=comparison,
                    spending_only=(
                        recipe_step
                        .spending_only
                    ),
                )
            )

        elif (
            operation
            == "rank_dimension"
        ):

            target = (
                self._get_period(
                    parameters,
                    recipe_step
                    .target_period_param,
                )
            )

            sql = (
                self._build_rank_dimension_sql(
                    target=target,
                    dimension=(
                        recipe_step
                        .dimension
                    ),
                    limit=(
                        recipe_step
                        .limit
                        or 10
                    ),
                    order=(
                        recipe_step
                        .order
                    ),
                    spending_only=(
                        recipe_step
                        .spending_only
                    ),
                )
            )

        elif (
            operation
            == "rank_dimension_delta"
        ):

            target = (
                self._get_period(
                    parameters,
                    recipe_step
                    .target_period_param,
                )
            )

            comparison = (
                self._get_period(
                    parameters,
                    recipe_step
                    .comparison_period_param,
                )
            )

            sql = (
                self._build_rank_dimension_delta_sql(
                    target=target,
                    comparison=comparison,
                    dimension=(
                        recipe_step
                        .dimension
                    ),
                    limit=(
                        recipe_step
                        .limit
                        or 10
                    ),
                    order=(
                        recipe_step
                        .order
                    ),
                    spending_only=(
                        recipe_step
                        .spending_only
                    ),
                )
            )

        elif (
            operation
            == "reconcile_dimension_delta"
        ):

            target = (
                self._get_period(
                    parameters,
                    recipe_step
                    .target_period_param,
                )
            )

            comparison = (
                self._get_period(
                    parameters,
                    recipe_step
                    .comparison_period_param,
                )
            )

            sql = (
                self._build_reconcile_delta_sql(
                    target=target,
                    comparison=comparison,
                    dimension=(
                        recipe_step
                        .dimension
                    ),
                    spending_only=(
                        recipe_step
                        .spending_only
                    ),
                )
            )

        elif (
            operation
            == "list_transactions"
        ):

            target = (
                self._get_period(
                    parameters,
                    recipe_step
                    .target_period_param,
                )
            )

            sql = (
                self._build_list_transactions_sql(
                    target=target,
                    limit=(
                        recipe_step
                        .limit
                        or 20
                    ),
                    spending_only=(
                        recipe_step
                        .spending_only
                    ),
                )
            )

        else:

            raise RecipeExecutionError(
                "Unsupported recipe operation: "
                f"{operation}"
            )

        try:

            result = (
                self.query_tool
                .execute(
                    sql
                )
            )

            return RecipeExecutionStep(
                step_id=(
                    recipe_step.step_id
                ),

                operation=operation,

                purpose=(
                    recipe_step.purpose
                ),

                status="ok",

                sql=sql,

                columns=(
                    result.columns
                ),

                rows=(
                    result.rows
                ),

                row_count=(
                    result.row_count
                ),

                truncated=(
                    result.truncated
                ),

                error=None,
            )

        except Exception as exc:

            return RecipeExecutionStep(
                step_id=(
                    recipe_step.step_id
                ),

                operation=operation,

                purpose=(
                    recipe_step.purpose
                ),

                status="error",

                sql=sql,

                error=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

    # =====================================================
    # SQL BUILDERS
    # =====================================================

    def _build_snapshot_sql(
        self,
    ) -> str:

        return """
        SELECT
            current_balance_minor,
            currency,
            balance_anchor_utc,
            latest_transaction_utc
        FROM v_financial_snapshot
        """.strip()

    def _build_aggregate_spending_sql(
        self,
        *,
        target: dict,
        spending_only: bool,
    ) -> str:

        where = (
            self._build_where(
                start=target["start"],
                end=target["end"],
                spending_only=spending_only,
            )
        )

        return f"""
        SELECT
            COALESCE(
                SUM(amount_minor),
                0
            ) / 100.0
                AS total_sar,

            COUNT(*)
                AS transaction_count

        FROM v_financial_transactions

        WHERE
            {where}
        """.strip()

    def _build_compare_periods_sql(
        self,
        *,
        target: dict,
        comparison: dict,
        spending_only: bool,
    ) -> str:

        date_expr = (
            self._local_date_expression()
        )

        filters = (
            self._base_filters(
                spending_only
            )
        )

        return f"""
        SELECT

            COALESCE(
                SUM(
                    CASE
                        WHEN {date_expr}
                            BETWEEN '{target["start"]}'
                            AND '{target["end"]}'
                        THEN amount_minor
                        ELSE 0
                    END
                ),
                0
            ) / 100.0
                AS target_sar,

            COALESCE(
                SUM(
                    CASE
                        WHEN {date_expr}
                            BETWEEN '{comparison["start"]}'
                            AND '{comparison["end"]}'
                        THEN amount_minor
                        ELSE 0
                    END
                ),
                0
            ) / 100.0
                AS comparison_sar,

            COUNT(
                CASE
                    WHEN {date_expr}
                        BETWEEN '{target["start"]}'
                        AND '{target["end"]}'
                    THEN 1
                END
            )
                AS target_transaction_count,

            COUNT(
                CASE
                    WHEN {date_expr}
                        BETWEEN '{comparison["start"]}'
                        AND '{comparison["end"]}'
                    THEN 1
                END
            )
                AS comparison_transaction_count,

            (
                COALESCE(
                    SUM(
                        CASE
                            WHEN {date_expr}
                                BETWEEN '{target["start"]}'
                                AND '{target["end"]}'
                            THEN amount_minor
                            ELSE 0
                        END
                    ),
                    0
                )
                -
                COALESCE(
                    SUM(
                        CASE
                            WHEN {date_expr}
                                BETWEEN '{comparison["start"]}'
                                AND '{comparison["end"]}'
                            THEN amount_minor
                            ELSE 0
                        END
                    ),
                    0
                )
            ) / 100.0
                AS delta_sar

        FROM v_financial_transactions

        WHERE
            {filters}
        """.strip()

    def _build_rank_dimension_sql(
        self,
        *,
        target: dict,
        dimension: str | None,
        limit: int,
        order: str | None,
        spending_only: bool,
    ) -> str:

        (
            view,
            expression,
        ) = (
            self._dimension_definition(
                dimension
            )
        )

        date_expr = (
            self._local_date_expression()
        )

        filters = (
            self._base_filters(
                spending_only
            )
        )

        order_sql = (
            "total_sar ASC"
            if order == "amount_asc"
            else (
                "transaction_count DESC"
                if order == "count_desc"
                else (
                    "transaction_count ASC"
                    if order == "count_asc"
                    else "total_sar DESC"
                )
            )
        )

        return f"""
        SELECT

            {expression}
                AS dimension_value,

            SUM(amount_minor) / 100.0
                AS total_sar,

            COUNT(
                DISTINCT transaction_id
            )
                AS transaction_count

        FROM {view}

        WHERE
            {filters}

            AND
            {date_expr}
                BETWEEN '{target["start"]}'
                AND '{target["end"]}'

        GROUP BY
            {expression}

        ORDER BY
            {order_sql}

        LIMIT {int(limit)}
        """.strip()

    def _build_rank_dimension_delta_sql(
        self,
        *,
        target: dict,
        comparison: dict,
        dimension: str | None,
        limit: int,
        order: str | None,
        spending_only: bool,
    ) -> str:

        (
            view,
            expression,
        ) = (
            self._dimension_definition(
                dimension
            )
        )

        date_expr = (
            self._local_date_expression()
        )

        filters = (
            self._base_filters(
                spending_only
            )
        )

        order_sql = (
            "delta_sar ASC"
            if order == "delta_asc"
            else "delta_sar DESC"
        )

        return f"""
        WITH base AS (

            SELECT

                COALESCE(
                    CAST(
                        {expression}
                        AS TEXT
                    ),
                    '(unknown)'
                )
                    AS dimension_value,

                COALESCE(
                    SUM(
                        CASE
                            WHEN {date_expr}
                                BETWEEN '{target["start"]}'
                                AND '{target["end"]}'
                            THEN amount_minor
                            ELSE 0
                        END
                    ),
                    0
                ) / 100.0
                    AS target_sar,

                COALESCE(
                    SUM(
                        CASE
                            WHEN {date_expr}
                                BETWEEN '{comparison["start"]}'
                                AND '{comparison["end"]}'
                            THEN amount_minor
                            ELSE 0
                        END
                    ),
                    0
                ) / 100.0
                    AS comparison_sar,

                COUNT(
                    DISTINCT
                    CASE
                        WHEN {date_expr}
                            BETWEEN '{target["start"]}'
                            AND '{target["end"]}'
                        THEN transaction_id
                    END
                )
                    AS target_count,

                COUNT(
                    DISTINCT
                    CASE
                        WHEN {date_expr}
                            BETWEEN '{comparison["start"]}'
                            AND '{comparison["end"]}'
                        THEN transaction_id
                    END
                )
                    AS comparison_count

            FROM {view}

            WHERE
                {filters}

                AND (
                    {date_expr}
                        BETWEEN '{target["start"]}'
                        AND '{target["end"]}'

                    OR

                    {date_expr}
                        BETWEEN '{comparison["start"]}'
                        AND '{comparison["end"]}'
                )

            GROUP BY
                {expression}
        )

        SELECT

            dimension_value,

            target_sar,

            comparison_sar,

            target_sar
                - comparison_sar
                AS delta_sar,

            target_count,

            comparison_count

        FROM base

        WHERE
            target_sar
            != comparison_sar

        ORDER BY
            {order_sql}

        LIMIT {int(limit)}
        """.strip()

    def _build_reconcile_delta_sql(
        self,
        *,
        target: dict,
        comparison: dict,
        dimension: str | None,
        spending_only: bool,
    ) -> str:

        # Concepts are multi-label.
        #
        # They cannot safely reconcile back to ledger
        # net change because totals may overlap.
        if dimension == "concept":

            raise RecipeExecutionError(
                "Concept deltas cannot be used "
                "for net-change reconciliation "
                "because concepts are multi-label."
            )

        (
            view,
            expression,
        ) = (
            self._dimension_definition(
                dimension
            )
        )

        date_expr = (
            self._local_date_expression()
        )

        filters = (
            self._base_filters(
                spending_only
            )
        )

        return f"""
        WITH base AS (

            SELECT

                COALESCE(
                    CAST(
                        {expression}
                        AS TEXT
                    ),
                    '(unknown)'
                )
                    AS dimension_value,

                COALESCE(
                    SUM(
                        CASE
                            WHEN {date_expr}
                                BETWEEN '{target["start"]}'
                                AND '{target["end"]}'
                            THEN amount_minor
                            ELSE 0
                        END
                    ),
                    0
                ) / 100.0
                    AS target_sar,

                COALESCE(
                    SUM(
                        CASE
                            WHEN {date_expr}
                                BETWEEN '{comparison["start"]}'
                                AND '{comparison["end"]}'
                            THEN amount_minor
                            ELSE 0
                        END
                    ),
                    0
                ) / 100.0
                    AS comparison_sar

            FROM {view}

            WHERE
                {filters}

                AND (
                    {date_expr}
                        BETWEEN '{target["start"]}'
                        AND '{target["end"]}'

                    OR

                    {date_expr}
                        BETWEEN '{comparison["start"]}'
                        AND '{comparison["end"]}'
                )

            GROUP BY
                {expression}
        ),

        deltas AS (

            SELECT

                target_sar
                - comparison_sar
                    AS delta_sar

            FROM base
        )

        SELECT

            COALESCE(
                SUM(
                    CASE
                        WHEN delta_sar > 0
                        THEN delta_sar
                        ELSE 0
                    END
                ),
                0
            )
                AS positive_change_sar,

            COALESCE(
                SUM(
                    CASE
                        WHEN delta_sar < 0
                        THEN delta_sar
                        ELSE 0
                    END
                ),
                0
            )
                AS negative_change_sar,

            COALESCE(
                SUM(
                    delta_sar
                ),
                0
            )
                AS net_change_sar

        FROM deltas
        """.strip()

    def _build_list_transactions_sql(
        self,
        *,
        target: dict,
        limit: int,
        spending_only: bool,
    ) -> str:

        where = (
            self._build_where(
                start=target["start"],
                end=target["end"],
                spending_only=spending_only,
            )
        )

        return f"""
        SELECT
            transaction_id,
            amount_minor,
            currency,
            direction,
            occurred_at_utc,
            merchant,
            description,
            financial_nature,
            concepts

        FROM v_financial_transactions

        WHERE
            {where}

        ORDER BY
            occurred_at_utc DESC

        LIMIT {int(limit)}
        """.strip()

    # =====================================================
    # SQL HELPERS
    # =====================================================

    def _build_where(
        self,
        *,
        start: str,
        end: str,
        spending_only: bool,
    ) -> str:

        return (
            self._base_filters(
                spending_only
            )
            + "\nAND "
            + self._local_date_expression()
            + f" BETWEEN '{start}' AND '{end}'"
        )

    @staticmethod
    def _base_filters(
        spending_only: bool,
    ) -> str:

        filters = [
            "status = 'posted'",
        ]

        if spending_only:

            filters.extend(
                [
                    "direction = 'debit'",
                    (
                        "financial_nature "
                        "= 'expense'"
                    ),
                ]
            )

        return "\nAND ".join(
            filters
        )

    def _local_date_expression(
        self,
    ) -> str:

        offset = (
            self._sqlite_offset()
        )

        return (
            "date("
            "datetime("
            "occurred_at_utc, "
            f"'{offset}'"
            ")"
            ")"
        )

    def _dimension_definition(
        self,
        dimension: str | None,
    ) -> tuple[
        str,
        str,
    ]:

        offset = (
            self._sqlite_offset()
        )

        definitions = {

            "merchant": (
                "v_financial_transactions",
                "merchant",
            ),

            "concept": (
                "v_financial_concepts",
                "concept",
            ),

            "financial_nature": (
                "v_financial_transactions",
                "financial_nature",
            ),

            "source": (
                "v_financial_transactions",
                "source",
            ),

            "day": (
                "v_financial_transactions",
                (
                    "strftime("
                    "'%d', "
                    "datetime("
                    "occurred_at_utc, "
                    f"'{offset}'"
                    ")"
                    ")"
                ),
            ),

            "weekday": (
                "v_financial_transactions",
                (
                    "strftime("
                    "'%w', "
                    "datetime("
                    "occurred_at_utc, "
                    f"'{offset}'"
                    ")"
                    ")"
                ),
            ),
        }

        if (
            dimension
            not in definitions
        ):

            raise RecipeExecutionError(
                "Unsupported analytical "
                f"dimension: {dimension}"
            )

        return definitions[
            dimension
        ]

    # =====================================================
    # PARAMETERS
    # =====================================================

    @staticmethod
    def _get_period(
        parameters: dict,
        name: str | None,
    ) -> dict:

        if not name:

            raise RecipeExecutionError(
                "Recipe step is missing "
                "a period parameter."
            )

        period = (
            parameters.get(
                name
            )
        )

        if not isinstance(
            period,
            dict,
        ):

            raise RecipeExecutionError(
                "Resolved period not found: "
                f"{name}"
            )

        return period

    # =====================================================
    # TIME
    # =====================================================

    def _sqlite_offset(
        self,
    ) -> str:

        now = datetime.now(
            self.timezone
        )

        offset = (
            now.utcoffset()
        )

        if offset is None:

            return "+00:00"

        total_minutes = int(
            offset.total_seconds()
            // 60
        )

        sign = (
            "+"
            if total_minutes >= 0
            else "-"
        )

        total_minutes = abs(
            total_minutes
        )

        hours, minutes = divmod(
            total_minutes,
            60,
        )

        return (
            f"{sign}"
            f"{hours:02d}:"
            f"{minutes:02d}"
        )

    @staticmethod
    def _parse_utc_datetime(
        value: str,
    ) -> datetime:

        normalized = (
            value.strip()
        )

        if normalized.endswith(
            "Z"
        ):

            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        parsed = (
            datetime.fromisoformat(
                normalized
            )
        )

        if (
            parsed.tzinfo
            is None
        ):

            parsed = (
                parsed.replace(
                    tzinfo=timezone.utc
                )
            )

        return parsed