from app.contracts.action_plan import (
    ActionPlan,
    CreateTransactionAction,
    QueryFinancialDataAction,
)

from app.contracts.results import (
    ActionExecutionResult,
    PlanExecutionResult,
)

from app.core.enums import (
    PlanStatus,
)

from app.core.execution_context import (
    get_external_message_id,
)

from app.modules.analytics.service import (
    AnalyticsService,
)

from app.modules.transactions.service import (
    DuplicateTransactionRequest,
    TransactionService,
)


class ActionExecutionError(Exception):
    pass


class ActionExecutor:

    def __init__(
        self,
        transaction_service:
            TransactionService | None = None,
        analytics_service:
            AnalyticsService | None = None,
    ):

        self.transactions = (
            transaction_service
            or TransactionService()
        )

        self.analytics = (
            analytics_service
            or AnalyticsService()
        )


    def execute(
        self,
        *,
        plan: ActionPlan,
        user_message: str | None = None,
    ) -> PlanExecutionResult:

        if plan.status != PlanStatus.READY:

            raise ActionExecutionError(
                "Only ready plans can be executed."
            )


        pending = {
            action.action_id: action
            for action in plan.actions
        }


        completed: set[str] = set()


        results: list[
            ActionExecutionResult
        ] = []


        while pending:

            progress = False


            for (
                action_id,
                action,
            ) in list(
                pending.items()
            ):

                if not set(
                    action.depends_on
                ).issubset(
                    completed
                ):

                    continue


                result = (
                    self._execute_action(
                        action=action,
                        user_message=(
                            user_message
                        ),
                    )
                )


                results.append(
                    result
                )


                completed.add(
                    action_id
                )


                del pending[
                    action_id
                ]


                progress = True


            if not progress:

                raise ActionExecutionError(
                    "Unable to resolve action "
                    "dependencies."
                )


        return PlanExecutionResult(
            actions=results
        )


    def _execute_action(
        self,
        *,
        action,
        user_message: str | None,
    ) -> ActionExecutionResult:

        if isinstance(
            action,
            CreateTransactionAction,
        ):

            return (
                self._execute_create_transaction(
                    action=action,
                    user_message=(
                        user_message
                    ),
                )
            )


        if isinstance(
            action,
            QueryFinancialDataAction,
        ):

            return (
                self._execute_query_financial_data(
                    action=action
                )
            )


        raise ActionExecutionError(
            "Action type is not implemented "
            f"yet: {action.type}"
        )


    def _execute_query_financial_data(
        self,
        *,
        action: QueryFinancialDataAction,
    ) -> ActionExecutionResult:

        result = self.analytics.query(
            action.parameters
        )


        return ActionExecutionResult(
            action_id=(
                action.action_id
            ),

            action_type=(
                "query_financial_data"
            ),

            data={
                "metric":
                    result.metric.value,

                "amount_minor":
                    result.amount_minor,

                "currency":
                    result.currency,

                "transaction_count":
                    result.transaction_count,

                "period_start_utc": (
                    result.period_start_utc
                    .isoformat()

                    if result.period_start_utc
                    else None
                ),

                "period_end_utc": (
                    result.period_end_utc
                    .isoformat()

                    if result.period_end_utc
                    else None
                ),

                "concepts":
                    result.concepts,
            },
        )


    def _execute_create_transaction(
        self,
        *,
        action: CreateTransactionAction,
        user_message: str | None,
    ) -> ActionExecutionResult:

        external_message_id = (
            get_external_message_id()
        )

        idempotency_key = (
            (
                f"{external_message_id}:"
                f"{action.action_id}"
            )
            if external_message_id
            else None
        )

        try:

            created = (
                self.transactions
                .create_transaction(
                    parameters=(
                        action.parameters
                    ),
                    raw_description=(
                        user_message
                    ),
                    idempotency_key=(
                        idempotency_key
                    ),
                )
            )

        except DuplicateTransactionRequest as exc:

            existing_data = (
                self.transactions
                .get_execution_data(
                    exc.transaction_id
                )
            )

            print(
                "\n"
                "[Transaction Idempotency] "
                "Existing write reused: "
                f"{exc.transaction_id}"
            )

            return ActionExecutionResult(
                action_id=(
                    action.action_id
                ),
                action_type=(
                    "create_transaction"
                ),
                data=existing_data,
            )

        tx = created.transaction
        annotation = created.annotation

        return ActionExecutionResult(
            action_id=action.action_id,

            action_type=(
                "create_transaction"
            ),

            data={
                "transaction_id":
                    tx.id,

                "amount_minor":
                    tx.amount_minor,

                "currency":
                    tx.currency,

                "direction":
                    tx.direction.value,

                "occurred_at_utc":
                    tx.occurred_at_utc.isoformat(),

                "merchant":
                    tx.merchant_raw_name,

                "financial_nature":
                    annotation
                    .financial_nature
                    .value,

                "concepts":
                    annotation.concepts,
            },
        )