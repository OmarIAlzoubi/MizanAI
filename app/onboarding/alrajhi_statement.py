from __future__ import annotations

import re

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.infrastructure.database.connection import (
    Database,
)


SAR = Decimal("0.01")

DATE_RE = re.compile(
    r"^\d{4}/\d{2}/\d{2}$"
)

SAR_VALUE_RE = re.compile(
    r"([\d,]+\.\d{2})\s+SAR"
)

TIME_RE = re.compile(
    r"Time:(\d{2}:\d{2}:\d{2})",
    re.IGNORECASE,
)


class StatementImportError(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class StatementTransaction:
    occurred_at_utc: datetime
    amount: Decimal
    balance: Decimal
    direction: str
    description: str
    merchant: str | None
    financial_nature: str


@dataclass(frozen=True)
class StatementPreview:
    opening_balance: Decimal
    closing_balance: Decimal

    period_start: str
    period_end: str

    expected_deposit_count: int
    expected_withdrawal_count: int

    expected_deposit_total: Decimal
    expected_withdrawal_total: Decimal

    transactions: tuple[
        StatementTransaction,
        ...
    ]

    @property
    def deposit_count(
        self,
    ) -> int:

        return sum(
            1
            for tx in self.transactions
            if tx.direction == "credit"
        )

    @property
    def withdrawal_count(
        self,
    ) -> int:

        return sum(
            1
            for tx in self.transactions
            if tx.direction == "debit"
        )

    @property
    def deposit_total(
        self,
    ) -> Decimal:

        return _money(
            sum(
                (
                    tx.amount
                    for tx in self.transactions
                    if tx.direction
                    == "credit"
                ),
                Decimal("0"),
            )
        )

    @property
    def withdrawal_total(
        self,
    ) -> Decimal:

        return _money(
            sum(
                (
                    tx.amount
                    for tx in self.transactions
                    if tx.direction
                    == "debit"
                ),
                Decimal("0"),
            )
        )


def parse_alrajhi_pdf(
    path: str | Path,
    *,
    timezone_name: str = (
        "Asia/Riyadh"
    ),
) -> StatementPreview:

    path = Path(path)

    if not path.exists():
        raise StatementImportError(
            f"Statement not found: {path}"
        )

    if path.suffix.lower() != ".pdf":
        raise StatementImportError(
            "The Al Rajhi adapter expects "
            "a PDF statement."
        )

    try:
        import fitz
    except ImportError as exc:
        raise StatementImportError(
            "PyMuPDF is required for PDF "
            "statement import. Install it "
            "with: pip install PyMuPDF"
        ) from exc

    document = fitz.open(
        path
    )

    try:
        text = "\n".join(
            page.get_text("text")
            for page in document
        )
    finally:
        document.close()

    if (
        "Account Statement"
        not in text
        or "Closing Balance"
        not in text
    ):
        raise StatementImportError(
            "This PDF does not look like "
            "a supported Al Rajhi account "
            "statement."
        )

    opening_balance = (
        _extract_money_after_label(
            text,
            "Opening Balance",
        )
    )

    closing_balance = (
        _extract_money_after_label(
            text,
            "Closing Balance",
        )
    )

    expected_deposits = (
        _extract_int_after_label(
            text,
            "Number Of Deposits",
        )
    )

    expected_withdrawals = (
        _extract_int_after_label(
            text,
            "Number Of Withdrawals",
        )
    )

    expected_deposit_total = (
        _extract_money_after_label(
            text,
            "Total Deposits",
        )
    )

    expected_withdrawal_total = (
        _extract_money_after_label(
            text,
            "Total Withdrawals",
        )
    )

    period_match = re.search(
        r"On The Period\s+"
        r"(\d{4}/\d{2}/\d{2})"
        r"\s*-\s*"
        r"(\d{4}/\d{2}/\d{2})",
        text,
        re.IGNORECASE,
    )

    if period_match is None:
        raise StatementImportError(
            "Could not read statement period."
        )

    period_start = (
        period_match.group(1)
    )

    period_end = (
        period_match.group(2)
    )

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    tz = ZoneInfo(
        timezone_name
    )

    transactions = []

    index = 0

    while index < len(lines):

        current = lines[index]

        if not DATE_RE.fullmatch(
            current
        ):
            index += 1
            continue

        date_text = current

        next_index = index + 1

        block = []

        while (
            next_index < len(lines)
            and not DATE_RE.fullmatch(
                lines[next_index]
            )
        ):
            block.append(
                lines[next_index]
            )
            next_index += 1

        money_values = []

        for line in block:
            money_values.extend(
                SAR_VALUE_RE.findall(
                    line
                )
            )

        # A transaction contains:
        # debit, credit, running balance.
        if len(money_values) >= 3:

            debit = _decimal(
                money_values[-3]
            )

            credit = _decimal(
                money_values[-2]
            )

            balance = _decimal(
                money_values[-1]
            )

            if (
                debit > 0
                or credit > 0
            ):

                direction = (
                    "debit"
                    if debit > 0
                    else "credit"
                )

                amount = (
                    debit
                    if debit > 0
                    else credit
                )

                time_match = (
                    TIME_RE.search(
                        " ".join(block)
                    )
                )

                time_text = (
                    time_match.group(1)
                    if time_match
                    else "12:00:00"
                )

                local_dt = datetime.strptime(
                    (
                        f"{date_text} "
                        f"{time_text}"
                    ),
                    "%Y/%m/%d %H:%M:%S",
                ).replace(
                    tzinfo=tz
                )

                occurred_utc = (
                    local_dt.astimezone(
                        timezone.utc
                    )
                )

                description = (
                    _clean_description(
                        block
                    )
                )

                merchant = (
                    _extract_merchant(
                        description
                    )
                )

                nature = (
                    _classify_nature(
                        description,
                        direction,
                    )
                )

                transactions.append(
                    StatementTransaction(
                        occurred_at_utc=(
                            occurred_utc
                        ),
                        amount=_money(
                            amount
                        ),
                        balance=_money(
                            balance
                        ),
                        direction=direction,
                        description=description,
                        merchant=merchant,
                        financial_nature=(
                            nature
                        ),
                    )
                )

        index = next_index

    preview = StatementPreview(
        opening_balance=(
            opening_balance
        ),
        closing_balance=(
            closing_balance
        ),
        period_start=period_start,
        period_end=period_end,
        expected_deposit_count=(
            expected_deposits
        ),
        expected_withdrawal_count=(
            expected_withdrawals
        ),
        expected_deposit_total=(
            expected_deposit_total
        ),
        expected_withdrawal_total=(
            expected_withdrawal_total
        ),
        transactions=tuple(
            transactions
        ),
    )

    _validate_integrity(
        preview
    )

    return preview


def import_statement(
    *,
    preview: StatementPreview,
    database: Database,
) -> int:

    if not preview.transactions:
        raise StatementImportError(
            "Statement contains no "
            "transactions."
        )

    created_at = (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )

    latest_utc = max(
        tx.occurred_at_utc
        for tx in preview.transactions
    ).isoformat()

    with database.session() as conn:

        existing_count = (
            conn.execute(
                """
                SELECT COUNT(*)
                FROM transactions
                """
            )
            .fetchone()[0]
        )

        if existing_count:
            raise StatementImportError(
                "The database already contains "
                "transactions. Statement import "
                "only runs against an empty "
                "ledger during onboarding."
            )

        imported = 0

        for tx in preview.transactions:

            tx_id = str(
                uuid4()
            )

            annotation_id = str(
                uuid4()
            )

            conn.execute(
                """
                INSERT INTO transactions (
                    id,
                    account_id,
                    amount_minor,
                    currency,
                    direction,
                    occurred_at_utc,
                    posted_at_utc,
                    status,
                    merchant_raw_name,
                    raw_description,
                    source,
                    created_at_utc
                )
                VALUES (
                    ?,
                    'primary',
                    ?,
                    'SAR',
                    ?,
                    ?,
                    ?,
                    'posted',
                    ?,
                    ?,
                    'bank_statement',
                    ?
                )
                """,
                (
                    tx_id,
                    _minor(
                        tx.amount
                    ),
                    tx.direction,
                    tx.occurred_at_utc
                    .isoformat(),
                    tx.occurred_at_utc
                    .isoformat(),
                    tx.merchant,
                    tx.description,
                    created_at,
                ),
            )

            conn.execute(
                """
                INSERT INTO
                semantic_annotations (
                    id,
                    transaction_id,
                    financial_nature,
                    source,
                    version,
                    is_active,
                    created_at_utc
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    'statement_rule',
                    1,
                    1,
                    ?
                )
                """,
                (
                    annotation_id,
                    tx_id,
                    tx.financial_nature,
                    created_at,
                ),
            )

            for concept in (
                _simple_concepts(
                    tx.description
                )
            ):

                conn.execute(
                    """
                    INSERT OR IGNORE INTO
                    annotation_concepts (
                        annotation_id,
                        concept
                    )
                    VALUES (?, ?)
                    """,
                    (
                        annotation_id,
                        concept,
                    ),
                )

            imported += 1

        _set_state(
            conn,
            key="balance_anchor_minor",
            value=str(
                _minor(
                    preview.closing_balance
                )
            ),
        )

        _set_state(
            conn,
            key="balance_anchor_utc",
            value=latest_utc,
        )

        _set_state(
            conn,
            key="bootstrap_source",
            value="alrajhi_statement",
        )

    return imported


def _validate_integrity(
    preview: StatementPreview,
) -> None:

    problems = []

    if (
        preview.deposit_count
        != preview.expected_deposit_count
    ):
        problems.append(
            "deposit count "
            f"{preview.deposit_count} != "
            f"{preview.expected_deposit_count}"
        )

    if (
        preview.withdrawal_count
        != preview.expected_withdrawal_count
    ):
        problems.append(
            "withdrawal count "
            f"{preview.withdrawal_count} != "
            f"{preview.expected_withdrawal_count}"
        )

    if (
        preview.deposit_total
        != preview.expected_deposit_total
    ):
        problems.append(
            "deposit total "
            f"{preview.deposit_total} != "
            f"{preview.expected_deposit_total}"
        )

    if (
        preview.withdrawal_total
        != preview.expected_withdrawal_total
    ):
        problems.append(
            "withdrawal total "
            f"{preview.withdrawal_total} != "
            f"{preview.expected_withdrawal_total}"
        )

    last_balance = (
        preview.transactions[-1].balance
        if preview.transactions
        else None
    )

    if (
        last_balance
        != preview.closing_balance
    ):
        problems.append(
            "last running balance "
            f"{last_balance} != "
            f"{preview.closing_balance}"
        )

    if problems:
        raise StatementImportError(
            "Statement integrity check failed: "
            + "; ".join(
                problems
            )
        )


def _extract_money_after_label(
    text: str,
    label: str,
) -> Decimal:

    match = re.search(
        re.escape(label)
        + r"\s+"
        + r"([\d,]+\.\d{2})\s+SAR",
        text,
        re.IGNORECASE,
    )

    if match is None:
        raise StatementImportError(
            f"Could not read {label}."
        )

    return _decimal(
        match.group(1)
    )


def _extract_int_after_label(
    text: str,
    label: str,
) -> int:

    match = re.search(
        re.escape(label)
        + r"\s+"
        + r"(\d+)",
        text,
        re.IGNORECASE,
    )

    if match is None:
        raise StatementImportError(
            f"Could not read {label}."
        )

    return int(
        match.group(1)
    )


def _clean_description(
    block: list[str],
) -> str:

    cleaned = []

    for line in block:

        without_money = (
            SAR_VALUE_RE.sub(
                "",
                line,
            )
            .strip()
        )

        if without_money:
            cleaned.append(
                without_money
            )

    return re.sub(
        r"\s+",
        " ",
        " ".join(
            cleaned
        ),
    ).strip()


def _extract_merchant(
    description: str,
) -> str | None:

    direct = re.search(
        r"Online Purchase from "
        r"([^,]+)",
        description,
        re.IGNORECASE,
    )

    if direct:

        value = (
            direct.group(1)
            .strip()
        )

        if value:
            return value[:120]

    notes = re.search(
        r"Notes:(.*)$",
        description,
        re.IGNORECASE,
    )

    if notes:

        candidate = (
            notes.group(1)
            .strip()
        )

        candidate = re.sub(
            r"^\([^)]*\)\s*",
            "",
            candidate,
        )

        candidate = re.sub(
            r",\s*(?:MADINA|AL Madinah|"
            r"RIYADH|JEDDAH)"
            r",\s*SA.*$",
            "",
            candidate,
            flags=re.IGNORECASE,
        )

        candidate = candidate.strip(
            " ,-"
        )

        if candidate:
            return candidate[:120]

    first = (
        description.split(
            " Time:",
            1,
        )[0]
        .strip()
    )

    return (
        first[:120]
        if first
        else None
    )


def _classify_nature(
    description: str,
    direction: str,
) -> str:

    value = (
        description.lower()
    )

    if (
        "refund" in value
        or "reversal" in value
    ):
        return "refund"

    if (
        "internal transfer"
        in value
        or value.startswith(
            "transfer "
        )
        or value == "transfer"
    ):
        return "transfer"

    if (
        "cash withdrawal"
        in value
        or "atm" in value
    ):
        return "cash_movement"

    if (
        "purchase" in value
        or "pos " in value
    ):
        return "expense"

    if (
        direction == "credit"
        and (
            "salary" in value
            or "payroll" in value
        )
    ):
        return "income"

    return "unknown"


def _simple_concepts(
    description: str,
) -> tuple[str, ...]:

    value = (
        description.lower()
    )

    concepts = []

    keyword_map = {
        "charity": (
            "ehsan",
            "إحسان",
        ),
        "telecom": (
            "stc",
            "mobily",
            "zain",
        ),
        "coffee": (
            "coffee",
            "cafe",
            "half million",
            "daily cup",
        ),
        "food": (
            "restaurant",
            "food",
            "chicken",
            "steakhouse",
        ),
        "shopping": (
            "amazon",
        ),
    }

    for concept, keywords in (
        keyword_map.items()
    ):

        if any(
            keyword.lower()
            in value
            for keyword in keywords
        ):
            concepts.append(
                concept
            )

    return tuple(
        concepts
    )


def _set_state(
    conn,
    *,
    key: str,
    value: str,
) -> None:

    conn.execute(
        """
        INSERT INTO app_state (
            key,
            value,
            updated_at_utc
        )
        VALUES (
            ?,
            ?,
            datetime('now')
        )
        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value,
            updated_at_utc =
                excluded.updated_at_utc
        """,
        (
            key,
            value,
        ),
    )


def _decimal(
    value: str,
) -> Decimal:

    return _money(
        Decimal(
            value.replace(
                ",",
                "",
            )
        )
    )


def _money(
    value: Decimal,
) -> Decimal:

    return value.quantize(
        SAR,
        rounding=(
            ROUND_HALF_UP
        ),
    )


def _minor(
    value: Decimal,
) -> int:

    return int(
        (
            value
            * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=(
                ROUND_HALF_UP
            ),
        )
    )
