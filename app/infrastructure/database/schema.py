from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)

from app.recipes.schema import (
    ensure_recipe_schema,
)

from app.modules.analytics.financial_views import (
    ensure_financial_views,
)

SCHEMA_STATEMENTS = [

    # =====================================================
    # ACCOUNTS
    #
    # موجود حاليًا لأن transactions تعتمد عليه في الـschema
    # لكننا لن نبني عليه أي منطق multi-account حاليًا.
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS accounts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        currency TEXT NOT NULL,
        created_at_utc TEXT NOT NULL
    )
    """,

    # =====================================================
    # TRANSACTIONS
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,

        account_id TEXT NOT NULL,

        amount_minor INTEGER NOT NULL,

        currency TEXT NOT NULL,

        direction TEXT NOT NULL,

        occurred_at_utc TEXT NOT NULL,

        posted_at_utc TEXT,

        status TEXT NOT NULL,

        merchant_raw_name TEXT,

        raw_description TEXT,

        source TEXT NOT NULL,

        created_at_utc TEXT NOT NULL,

        FOREIGN KEY (
            account_id
        )
        REFERENCES accounts(id)
        ON DELETE CASCADE
    )
    """,

    # =====================================================
    # SEMANTIC ANNOTATIONS
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS semantic_annotations (
        id TEXT PRIMARY KEY,

        transaction_id TEXT NOT NULL,

        financial_nature TEXT,

        source TEXT NOT NULL,

        version INTEGER NOT NULL,

        is_active INTEGER NOT NULL DEFAULT 1,

        created_at_utc TEXT NOT NULL,

        FOREIGN KEY (
            transaction_id
        )
        REFERENCES transactions(id)
        ON DELETE CASCADE
    )
    """,

    # =====================================================
    # ANNOTATION CONCEPTS
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS annotation_concepts (
        annotation_id TEXT NOT NULL,

        concept TEXT NOT NULL,

        PRIMARY KEY (
            annotation_id,
            concept
        ),

        FOREIGN KEY (
            annotation_id
        )
        REFERENCES semantic_annotations(id)
        ON DELETE CASCADE
    )
    """,

    # =====================================================
    # APP STATE
    #
    # Personal-app state only.
    # Example:
    #
    # current balance anchor
    # balance anchor timestamp
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS app_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at_utc TEXT NOT NULL
    )
    """,

    # =====================================================
    # PROCESSED INBOUND MESSAGES
    #
    # Prevent duplicate processing of external messages.
    # Twilio MessageSid is the idempotency key.
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS processed_inbound_messages (
        message_sid TEXT PRIMARY KEY,

        source TEXT NOT NULL,

        processed_at_utc TEXT NOT NULL,

        reply TEXT
    )
    """,

    # =====================================================
    # TRANSACTION IDEMPOTENCY
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS transaction_idempotency (
        idempotency_key TEXT PRIMARY KEY,

        transaction_id TEXT UNIQUE,

        created_at_utc TEXT NOT NULL,

        FOREIGN KEY (
            transaction_id
        )
        REFERENCES transactions(id)
        ON DELETE CASCADE
    )
    """,

    # =====================================================
    # OUTBOUND MESSAGES
    #
    # Durable ledger for replies sent through Twilio.
    #
    # One outbound reply per inbound MessageSid.
    # =====================================================

    """
    CREATE TABLE IF NOT EXISTS outbound_messages (
        inbound_message_sid TEXT PRIMARY KEY,

        provider TEXT NOT NULL,

        from_address TEXT NOT NULL,

        to_address TEXT NOT NULL,

        body TEXT NOT NULL,

        status TEXT NOT NULL,

        twilio_message_sid TEXT UNIQUE,

        created_at_utc TEXT NOT NULL,

        send_started_at_utc TEXT,

        sent_at_utc TEXT,

        last_error TEXT
    )
    """,

    # =====================================================
    # INDEXES
    # =====================================================

    """
    CREATE INDEX IF NOT EXISTS
    idx_transactions_account_id
    ON transactions(account_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_transactions_occurred_at
    ON transactions(occurred_at_utc)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_transactions_status
    ON transactions(status)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_transactions_direction
    ON transactions(direction)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_transactions_source
    ON transactions(source)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_semantic_annotations_transaction
    ON semantic_annotations(transaction_id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_semantic_annotations_active
    ON semantic_annotations(
        transaction_id,
        is_active
    )
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_semantic_annotations_financial_nature
    ON semantic_annotations(financial_nature)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_annotation_concepts_concept
    ON annotation_concepts(concept)
    """,
]


def initialize_database(
    database: Database | None = None,
) -> None:

    database = (
        database
        or get_default_database()
    )

    with database.session() as conn:

        # =================================================
        # CORE SCHEMA
        # =================================================

        for statement in SCHEMA_STATEMENTS:

            conn.execute(
                statement
            )

        # =================================================
        # PRIMARY ACCOUNT COMPATIBILITY
        # =================================================

        # Current system still expects primary account.
        # We keep this only for compatibility.

        conn.execute(
            """
            INSERT OR IGNORE INTO accounts (
                id,
                name,
                currency,
                created_at_utc
            )
            VALUES (
                'primary',
                'Primary',
                'SAR',
                datetime('now')
            )
            """
        )

        # =================================================
        # LIGHTWEIGHT SCHEMA MIGRATIONS
        # =================================================

        transaction_columns = {
            row["name"]

            for row in conn.execute(
                """
                PRAGMA table_info(transactions)
                """
            ).fetchall()
        }

        if (
            "posted_at_utc"
            not in transaction_columns
        ):

            conn.execute(
                """
                ALTER TABLE transactions
                ADD COLUMN posted_at_utc TEXT
                """
            )

        # =================================================
        # RECIPE SYSTEM SCHEMA
        # =================================================

        ensure_recipe_schema(
            conn
        )

        # =================================================
        # ANALYTICAL VIEWS
        # =================================================

        ensure_financial_views(
            conn
        )