from app.modules.transactions.service import (
    TransactionService,
)


transaction_service = (
    TransactionService()
)


def get_activity(
    limit: int = 50,
):
    transactions = (
        transaction_service.list_activity(
            limit=limit
        )
    )

    return {
        "transactions": [
            transaction.model_dump(
                mode="json"
            )
            for transaction
            in transactions
        ],

        "count": len(
            transactions
        ),
    }