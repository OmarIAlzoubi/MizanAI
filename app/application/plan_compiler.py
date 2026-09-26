from app.contracts.action_plan import (
    ActionPlan,
)
from app.contracts.llm_plan import (
    LLMActionPlan,
    LLMConversationResponseAction,
    LLMCreateTransactionAction,
    LLMQueryFinancialDataAction,
    LLMUpdateTransactionAction,
)
from app.core.enums import (
    ComparisonType,
    Metric,
    PeriodType,
)

class PlanCompilationError(Exception):
    pass


def _build_semantics(
    *,
    inferred_nature,
    inferred_concepts,
    asserted_nature,
    asserted_concepts,
):
    semantic_hint = None
    user_asserted = None

    if (
        inferred_nature is not None
        or inferred_concepts
    ):
        semantic_hint = {
            "financial_nature":
                inferred_nature,

            "concepts":
                inferred_concepts,
        }

    if (
        asserted_nature is not None
        or asserted_concepts
    ):
        user_asserted = {
            "financial_nature":
                asserted_nature,

            "concepts":
                asserted_concepts,
        }

    return semantic_hint, user_asserted


def _compile_create_transaction(
    action: LLMCreateTransactionAction,
):
    p = action.parameters

    semantic_hint, user_asserted = (
        _build_semantics(
            inferred_nature=(
                p.inferred_financial_nature
            ),
            inferred_concepts=(
                p.inferred_concepts
            ),
            asserted_nature=(
                p.asserted_financial_nature
            ),
            asserted_concepts=(
                p.asserted_concepts
            ),
        )
    )

    occurred_on = {
        "type": p.date_type,
        "offset": p.day_offset,
        "date": p.exact_date,
    }

    return {
        "action_id": action.action_id,

        "type": "create_transaction",

        "depends_on": action.depends_on,

        "parameters": {
            "amount_minor":
                p.amount_minor,

            "currency":
                p.currency.upper(),

            "direction":
                p.direction,

            "occurred_on":
                occurred_on,

            "merchant_raw_name":
                p.merchant,

            "semantic_hint":
                semantic_hint,

            "user_asserted_semantics":
                user_asserted,
        },
    }


def _compile_update_transaction(
    action: LLMUpdateTransactionAction,
):
    p = action.parameters

    target = {}

    if p.transaction_id:
        target["transaction_id"] = (
            p.transaction_id
        )

    if p.reference:
        target["reference"] = p.reference

    if p.target_merchant:
        target["merchant"] = (
            p.target_merchant
        )

    if p.target_amount_minor:
        target["amount_minor"] = (
            p.target_amount_minor
        )

    if p.target_period_type:
        target["period"] = {
            "type":
                p.target_period_type,

            "offset":
                p.target_period_offset,
        }

    changes = {}

    if p.new_amount_minor:
        changes["amount_minor"] = (
            p.new_amount_minor
        )

    if p.new_merchant:
        changes["merchant_raw_name"] = (
            p.new_merchant
        )

    semantic_hint, user_asserted = (
        _build_semantics(
            inferred_nature=(
                p.inferred_financial_nature
            ),
            inferred_concepts=(
                p.inferred_concepts
            ),
            asserted_nature=(
                p.asserted_financial_nature
            ),
            asserted_concepts=(
                p.asserted_concepts
            ),
        )
    )

    # For an UPDATE, explicit user semantics
    # must win over model inference.
    semantic = (
        user_asserted
        if user_asserted is not None
        else semantic_hint
    )

    if semantic is not None:
        changes["semantic"] = semantic

    return {
        "action_id": action.action_id,

        "type": "update_transaction",

        "depends_on": action.depends_on,

        "parameters": {
            "target": target,
            "changes": changes,
        },
    }


def _compile_query(
    action: LLMQueryFinancialDataAction,
):
    p = action.parameters

    # =========================================================
    # BALANCE
    #
    # Current balance is a snapshot, not a period-based metric.
    #
    # The LLM may still emit an irrelevant/invalid period such
    # as absolute_range without dates. Normalize it here so the
    # deterministic contract remains valid.
    # =========================================================

    if p.metric == Metric.BALANCE:

        period = {
            "type":
                PeriodType.CALENDAR_DAY,

            "offset":
                0,
        }

    else:

        period = {
            "type":
                p.period_type,

            "offset":
                p.period_offset,
        }


    if (
        p.metric != Metric.BALANCE
        and p.days is not None
    ):

        period["days"] = (
            p.days
        )


    if (
        p.metric != Metric.BALANCE
        and p.months is not None
    ):

        period["months"] = (
            p.months
        )


    if (
        p.metric != Metric.BALANCE
        and p.start_date is not None
    ):

        period["start_date"] = (
            p.start_date
        )


    if (
        p.metric != Metric.BALANCE
        and p.end_date is not None
    ):

        period["end_date"] = (
            p.end_date
        )

    # Do not fabricate missing period fields here.
    # PeriodSpec remains the deterministic validator.
    # If a read-only LLM plan is malformed, UnderstandingService
    # can safely route it to the Financial Agent instead of
    # returning HTTP 500.

    comparison = None

    if p.comparison is not None:
        comparison = {
            "type":
                ComparisonType(
                    p.comparison
                )
        }

    return {
        "action_id": action.action_id,

        "type": "query_financial_data",

        "depends_on": action.depends_on,

        "parameters": {
            "metric": p.metric,

            "period": period,

            "filters": {
                "concepts":
                    p.concepts,

                "merchants":
                    p.merchants,

                "financial_natures":
                    p.financial_natures,
            },

            "group_by":
                p.group_by,

            "comparison":
                comparison,

            "sort":
                p.sort,

            "limit":
                p.limit,
        },
    }


def _compile_conversation(
    action: LLMConversationResponseAction,
):
    return {
        "action_id": action.action_id,

        "type": "conversation_response",

        "depends_on": action.depends_on,

        "parameters": {
            "mode":
                action.parameters.mode,

            "topic":
                action.parameters.topic,
        },
    }


def compile_llm_plan(
    llm_plan: LLMActionPlan,
) -> ActionPlan:

    compiled_actions = []

    for action in llm_plan.actions:

        if isinstance(
            action,
            LLMCreateTransactionAction,
        ):
            compiled = (
                _compile_create_transaction(
                    action
                )
            )

        elif isinstance(
            action,
            LLMUpdateTransactionAction,
        ):
            compiled = (
                _compile_update_transaction(
                    action
                )
            )

        elif isinstance(
            action,
            LLMQueryFinancialDataAction,
        ):
            compiled = (
                _compile_query(
                    action
                )
            )

        elif isinstance(
            action,
            LLMConversationResponseAction,
        ):
            compiled = (
                _compile_conversation(
                    action
                )
            )

        else:
            raise PlanCompilationError(
                f"Unsupported LLM action: "
                f"{type(action).__name__}"
            )

        compiled_actions.append(
            compiled
        )

    payload = {
        "plan_version":
            llm_plan.plan_version,

        "status":
            llm_plan.status,

        "actions":
            compiled_actions,

        "clarification":
            (
                llm_plan.clarification
                .model_dump()
                if llm_plan.clarification
                else None
            ),

        "unsupported_reason":
            llm_plan.unsupported_reason,
    }

    try:
        return ActionPlan.model_validate(
            payload
        )

    except Exception as exc:
        raise PlanCompilationError(
            f"Compiled ActionPlan is invalid:\n"
            f"{exc}"
        ) from exc