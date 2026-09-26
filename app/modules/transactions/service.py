from dataclasses import dataclass

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4


from app.contracts.action_plan import (
    CreateTransactionParameters,
)

from app.core.enums import (
    FinancialNature,
)

from app.core.time import (
    resolve_transaction_date,
)

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)

from app.modules.transactions.models import (
    ActivityTransactionRecord,
    SemanticAnnotationRecord,
    TransactionRecord,
)

from app.modules.transactions.repository import (
    SemanticAnnotationRepository,
    TransactionIdempotencyRepository,
    TransactionRepository,
)


@dataclass(frozen=True)
class CreatedTransaction:
    transaction: TransactionRecord
    annotation: SemanticAnnotationRecord

class DuplicateTransactionRequest(Exception):

    def __init__(
        self,
        transaction_id: str,
    ):

        super().__init__(
            "Transaction request "
            "was already processed."
        )

        self.transaction_id = (
            transaction_id
        )


class TransactionService:

    def get_execution_data(
        self,
        transaction_id: str,
    ) -> dict:

        with self.database.session() as conn:

            row = (
                self.transactions
                .get_execution_data(
                    conn,
                    transaction_id,
                )
            )


        if row is None:

            raise RuntimeError(
                "Existing transaction "
                "could not be loaded."
            )


        raw_concepts = (
            row["concepts"]
            or ""
        )


        concepts = [
            concept
            for concept
            in raw_concepts.split("|")
            if concept
        ]


        return {
            "transaction_id":
                row["transaction_id"],

            "amount_minor":
                row["amount_minor"],

            "currency":
                row["currency"],

            "direction":
                row["direction"],

            "occurred_at_utc":
                row["occurred_at_utc"],

            "merchant":
                row["merchant"],

            "financial_nature":
                row["financial_nature"],

            "concepts":
                concepts,
        }

    def list_activity(
        self,
        *,
        limit: int = 50,
    ) -> list[ActivityTransactionRecord]:

        with self.database.session() as conn:

            rows = (
                self.transactions.list_recent(
                    conn,
                    limit=limit,
                )
            )

        results = []

        for row in rows:

            raw_concepts = (
                row["concepts"]
                or ""
            )

            concepts = [
                concept
                for concept
                in raw_concepts.split(",")
                if concept
            ]

            results.append(
                ActivityTransactionRecord(
                    id=row["id"],

                    amount_minor=(
                        row["amount_minor"]
                    ),

                    currency=(
                        row["currency"]
                    ),

                    direction=(
                        row["direction"]
                    ),

                    occurred_at_utc=(
                        row["occurred_at_utc"]
                    ),

                    merchant_raw_name=(
                        row["merchant_raw_name"]
                    ),

                    raw_description=(
                        row["raw_description"]
                    ),

                    financial_nature=(
                        row["financial_nature"]
                    ),

                    concepts=concepts,
                )
            )

        return results

    def __init__(
        self,
        database: Database | None = None,

        transaction_repository:
            TransactionRepository | None = None,

        annotation_repository:
            SemanticAnnotationRepository | None = None,

        idempotency_repository:
            TransactionIdempotencyRepository
            | None = None,
    ):

        self.database = (
            database
            or get_default_database()
        )

        self.transactions = (
            transaction_repository
            or TransactionRepository()
        )

        self.annotations = (
            annotation_repository
            or SemanticAnnotationRepository()
        )

        self.idempotency = (
            idempotency_repository
            or TransactionIdempotencyRepository()
        )

    def create_transaction(
        self,
        *,
        parameters: CreateTransactionParameters,
        raw_description: str | None = None,
        account_id: str = "primary",
        idempotency_key: str | None = None,
    ) -> CreatedTransaction:

        occurred_local = (
            resolve_transaction_date(
                parameters.occurred_on
            )
        )

        occurred_utc = (
            occurred_local
            .astimezone(timezone.utc)
        )

        created_utc = datetime.now(
            timezone.utc
        )

        (
            financial_nature,
            concepts,
            annotation_source,
        ) = self._resolve_semantics(
            parameters
        )

        transaction = TransactionRecord(
            id=str(uuid4()),

            account_id=account_id,

            amount_minor=(
                parameters.amount_minor
            ),

            currency=(
                parameters.currency.upper()
            ),

            direction=(
                parameters.direction
            ),

            occurred_at_utc=occurred_utc,

            merchant_raw_name=(
                parameters.merchant_raw_name
            ),

            raw_description=(
                raw_description
            ),

            source="chat",

            created_at_utc=created_utc,
        )

        annotation = (
            SemanticAnnotationRecord(
                id=str(uuid4()),

                transaction_id=(
                    transaction.id
                ),

                financial_nature=(
                    financial_nature
                ),

                concepts=concepts,

                source=annotation_source,

                version=1,

                is_active=True,

                created_at_utc=created_utc,
            )
        )

        # Transaction + annotation are written
        # atomically.
        #
        # If either one fails, both roll back.
        with self.database.session() as conn:

            if idempotency_key:

                (
                    claimed,
                    existing_transaction_id,
                ) = (
                    self.idempotency.claim(
                        conn,
                        idempotency_key=(
                            idempotency_key
                        ),
                        created_at_utc=(
                            created_utc.isoformat()
                        ),
                    )
                )


                if not claimed:

                    raise (
                        DuplicateTransactionRequest(
                            existing_transaction_id
                        )
                    )


            self.transactions.create(
                conn,
                transaction,
            )


            self.annotations.create(
                conn,
                annotation,
            )


            if idempotency_key:

                self.idempotency.bind_transaction(
                    conn,
                    idempotency_key=(
                        idempotency_key
                    ),
                    transaction_id=(
                        transaction.id
                    ),
                )

        return CreatedTransaction(
            transaction=transaction,
            annotation=annotation,
        )

    @staticmethod
    def _resolve_semantics(
        parameters:
            CreateTransactionParameters,
    ) -> tuple[
        FinancialNature,
        list[str],
        str,
    ]:

        inferred = (
            parameters.semantic_hint
        )

        asserted = (
            parameters
            .user_asserted_semantics
        )

        # ----------------------------------
        # FINANCIAL NATURE
        # ----------------------------------

        if (
            asserted
            and asserted.financial_nature
        ):
            financial_nature = (
                asserted.financial_nature
            )

        elif (
            inferred
            and inferred.financial_nature
        ):
            financial_nature = (
                inferred.financial_nature
            )

        else:
            financial_nature = (
                FinancialNature.UNKNOWN
            )

        # ----------------------------------
        # CONCEPTS
        # ----------------------------------

        concepts: list[str] = []

        if asserted:
            concepts.extend(
                asserted.concepts
            )

        if inferred:
            for concept in inferred.concepts:
                if concept not in concepts:
                    concepts.append(
                        concept
                    )

        concepts = [
            concept.strip().lower()
            for concept in concepts
            if concept.strip()
        ]

        # Preserve order while removing
        # duplicates.
        concepts = list(
            dict.fromkeys(concepts)
        )

        # ----------------------------------
        # SOURCE
        # ----------------------------------

        has_asserted = bool(
            asserted
            and (
                asserted.financial_nature
                or asserted.concepts
            )
        )

        has_inferred = bool(
            inferred
            and (
                inferred.financial_nature
                or inferred.concepts
            )
        )

        if has_asserted and has_inferred:
            source = "mixed"

        elif has_asserted:
            source = "user_asserted"

        elif has_inferred:
            source = "llm_inference"

        else:
            source = "system"

        return (
            financial_nature,
            concepts,
            source,
        )