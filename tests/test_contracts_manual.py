from app.contracts.action_plan import (
    ActionPlan,
)
from app.contracts.query_spec import QuerySpec
from app.core.time import resolve_period


query = QuerySpec.model_validate(
    {
        "metric": "spending",
        "period": {
            "type": "calendar_month",
            "offset": 0,
        },
        "filters": {
            "concepts": [
                "charity"
            ]
        },
    }
)

print("\nQUERY SPEC")
print(
    query.model_dump_json(
        indent=2
    )
)

resolved = resolve_period(
    query.period
)

print("\nRESOLVED PERIOD")
print("FROM:", resolved.start)
print("TO:  ", resolved.end)


plan = ActionPlan.model_validate(
    {
        "plan_version": "1.0",

        "status": "ready",

        "actions": [
            {
                "action_id": "a1",

                "type": "query_financial_data",

                "depends_on": [],

                "parameters": {
                    "metric": "spending",

                    "period": {
                        "type": "calendar_month",
                        "offset": 0
                    },

                    "filters": {
                        "concepts": [
                            "charity"
                        ]
                    }
                }
            }
        ]
    }
)

print("\nACTION PLAN")
print(
    plan.model_dump_json(
        indent=2
    )
)