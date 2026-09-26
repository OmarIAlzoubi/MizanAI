from __future__ import annotations

import re

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from threading import RLock
from typing import Literal

from app.ai.receipt_parser import ReceiptData


MONEY_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class PendingReceipt:
    merchant: str
    total_amount: Decimal
    currency: str
    transaction_date: str | None
    receipt_number: str | None
    confidence: float


@dataclass(frozen=True)
class ReceiptFollowupDecision:
    kind: Literal[
        "full",
        "partial",
        "cancel",
        "invalid",
        "none",
    ]
    amount: Decimal | None = None
    reason: str | None = None


class PendingReceiptStore:
    """
    Demo-only, process-local pending receipt memory.

    Keyed by the inbound WhatsApp address.
    It intentionally resets when the worker restarts.
    """

    def __init__(self):
        self._lock = RLock()
        self._items: dict[str, PendingReceipt] = {}

    def put(
        self,
        *,
        user_key: str,
        receipt: ReceiptData,
    ) -> PendingReceipt:

        user_key = user_key.strip()

        if not user_key:
            raise ValueError(
                "user_key cannot be empty."
            )

        if not receipt.is_receipt:
            raise ValueError(
                "Cannot store a non-receipt."
            )

        if receipt.total_amount is None:
            raise ValueError(
                "Receipt has no total amount."
            )

        if not receipt.merchant:
            raise ValueError(
                "Receipt has no merchant."
            )

        if not receipt.currency:
            raise ValueError(
                "Receipt has no currency."
            )

        total = _money(
            Decimal(str(receipt.total_amount))
        )

        if total <= 0:
            raise ValueError(
                "Receipt total must be positive."
            )

        pending = PendingReceipt(
            merchant=receipt.merchant.strip(),
            total_amount=total,
            currency=receipt.currency.strip().upper(),
            transaction_date=(
                receipt.transaction_date.strip()
                if receipt.transaction_date
                else None
            ),
            receipt_number=(
                receipt.receipt_number.strip()
                if receipt.receipt_number
                else None
            ),
            confidence=float(
                receipt.confidence
            ),
        )

        with self._lock:
            self._items[user_key] = pending

        return pending

    def get(
        self,
        user_key: str,
    ) -> PendingReceipt | None:

        with self._lock:
            return self._items.get(
                user_key.strip()
            )

    def pop(
        self,
        user_key: str,
    ) -> PendingReceipt | None:

        with self._lock:
            return self._items.pop(
                user_key.strip(),
                None,
            )

    def clear(
        self,
        user_key: str,
    ) -> None:

        self.pop(user_key)


def interpret_receipt_followup(
    *,
    text: str,
    receipt: PendingReceipt,
) -> ReceiptFollowupDecision:

    normalized = _normalize_text(
        text
    )

    if not normalized:
        return ReceiptFollowupDecision(
            kind="none"
        )

    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    cancel_exact = {
        "لا",
        "لا شكرا",
        "لا شكرًا",
        "الغ",
        "الغي",
        "الغها",
        "الغيها",
        "إلغاء",
        "الغاء",
        "لا تسجل",
        "لا تسجلها",
        "لا تحسبها",
    }

    if (
        normalized in cancel_exact
        or "لا تسجل" in normalized
        or "الغ الفاتورة" in normalized
        or "الغي الفاتورة" in normalized
    ):
        return ReceiptFollowupDecision(
            kind="cancel"
        )

    # -----------------------------------------------------
    # FRACTIONS
    # -----------------------------------------------------

    fraction_phrases = (
        (
            (
                "نصها",
                "نصفها",
                "نص المبلغ",
                "نصف المبلغ",
                "النص",
                "النصف",
            ),
            Decimal("0.5"),
        ),
        (
            (
                "ثلثينها",
                "ثلثيها",
                "ثلثين المبلغ",
            ),
            (
                Decimal("2")
                / Decimal("3")
            ),
        ),
        (
            (
                "ثلثها",
                "ثلث المبلغ",
                "الثلث",
            ),
            (
                Decimal("1")
                / Decimal("3")
            ),
        ),
        (
            (
                "ربعها",
                "ربع المبلغ",
                "الربع",
            ),
            Decimal("0.25"),
        ),
        (
            (
                "ثلاث ارباعها",
                "ثلاثة ارباعها",
                "ثلاث أرباعها",
                "ثلاثة أرباعها",
            ),
            Decimal("0.75"),
        ),
    )

    for phrases, fraction in (
        fraction_phrases
    ):
        if any(
            phrase in normalized
            for phrase in phrases
        ):
            amount = _money(
                receipt.total_amount
                * fraction
            )

            return ReceiptFollowupDecision(
                kind="partial",
                amount=amount,
                reason=(
                    f"fraction:{fraction}"
                ),
            )

    # -----------------------------------------------------
    # PERCENTAGE
    # Supports:
    # 50%
    # 50 بالمية
    # 50 بالمئة
    # -----------------------------------------------------

    percentage_match = re.search(
        r"(?<!\d)"
        r"(\d+(?:\.\d+)?)"
        r"\s*"
        r"(?:%|بالمية|بالمئه|بالمئة)"
        r"(?!\d)",
        normalized,
    )

    if percentage_match:

        try:
            percentage = Decimal(
                percentage_match.group(1)
            )
        except InvalidOperation:
            percentage = Decimal("-1")

        if (
            percentage <= 0
            or percentage > 100
        ):
            return ReceiptFollowupDecision(
                kind="invalid",
                reason=(
                    "النسبة لازم تكون أكبر من 0 "
                    "وأقل من أو تساوي 100%."
                ),
            )

        amount = _money(
            receipt.total_amount
            * percentage
            / Decimal("100")
        )

        return ReceiptFollowupDecision(
            kind="partial",
            amount=amount,
            reason=(
                f"percentage:{percentage}"
            ),
        )

    # -----------------------------------------------------
    # EXPLICIT AMOUNT
    # Supports:
    # دفعت 20 ريال
    # دفعت منها 24.50
    # أنا دفعت 10
    # -----------------------------------------------------

    if any(
        word in normalized
        for word in (
            "دفعت",
            "دافع",
            "علي",
            "حصتي",
        )
    ):

        amount_match = re.search(
            r"(?<!\d)"
            r"(\d+(?:\.\d{1,2})?)"
            r"(?!\d)",
            normalized,
        )

        if amount_match:

            try:
                amount = _money(
                    Decimal(
                        amount_match.group(1)
                    )
                )
            except InvalidOperation:
                amount = Decimal("-1")

            if amount <= 0:
                return ReceiptFollowupDecision(
                    kind="invalid",
                    reason=(
                        "المبلغ لازم يكون أكبر من صفر."
                    ),
                )

            if amount > receipt.total_amount:
                return ReceiptFollowupDecision(
                    kind="invalid",
                    reason=(
                        "المبلغ الذي ذكرته أكبر "
                        "من إجمالي الفاتورة."
                    ),
                )

            kind = (
                "full"
                if amount
                == receipt.total_amount
                else "partial"
            )

            return ReceiptFollowupDecision(
                kind=kind,
                amount=amount,
                reason="explicit_amount",
            )

    # -----------------------------------------------------
    # FULL CONFIRMATION
    # -----------------------------------------------------

    full_exact = {
        "نعم",
        "ايه",
        "ايوه",
        "أيوه",
        "أكيد",
        "اكيد",
        "سجل",
        "سجلها",
        "سجل الفاتورة",
        "كلها",
        "كامل",
        "كاملها",
        "دفعتها كلها",
        "دفعت كلها",
        "دفعت كاملها",
        "دفعت كامل المبلغ",
        "احسبها كلها",
    }

    if (
        normalized in full_exact
        or "سجلها كلها" in normalized
        or "دفعت الفاتورة كاملة"
        in normalized
    ):
        return ReceiptFollowupDecision(
            kind="full",
            amount=receipt.total_amount,
            reason="full_confirmation",
        )

    return ReceiptFollowupDecision(
        kind="none"
    )


def build_transaction_message(
    *,
    receipt: PendingReceipt,
    amount: Decimal,
) -> str:

    amount = _money(
        amount
    )

    currency_phrase = (
        "ريال"
        if receipt.currency == "SAR"
        else receipt.currency
    )

    message = (
        f"دفعت {amount:.2f} "
        f"{currency_phrase} "
        f"في {receipt.merchant}"
    )

    if receipt.transaction_date:
        message += (
            " بتاريخ "
            f"{receipt.transaction_date}"
        )

    return message


def format_receipt_confirmation(
    receipt: PendingReceipt,
) -> str:

    date_line = (
        f"\nالتاريخ: {receipt.transaction_date}"
        if receipt.transaction_date
        else ""
    )

    return (
        "قرأت الفاتورة ✅\n"
        f"التاجر: {receipt.merchant}\n"
        f"الإجمالي: "
        f"{receipt.total_amount:.2f} "
        f"{receipt.currency}"
        f"{date_line}\n\n"
        "تقدر تقول: "
        "«سجلها»، "
        "«دفعت نصها»، "
        "«دفعت 20 ريال»، "
        "أو «إلغاء»."
    )


def format_partial_confirmation(
    *,
    receipt: PendingReceipt,
    amount: Decimal,
) -> str:

    return (
        "تم تسجيل حصتك من الفاتورة ✅\n"
        f"المبلغ: {amount:.2f} "
        f"{receipt.currency}\n"
        f"من إجمالي: "
        f"{receipt.total_amount:.2f} "
        f"{receipt.currency}\n"
        f"التاجر: {receipt.merchant}"
    )


def _money(
    value: Decimal,
) -> Decimal:

    return value.quantize(
        MONEY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )


def _normalize_text(
    text: str,
) -> str:

    translation = str.maketrans(
        {
            "٠": "0",
            "١": "1",
            "٢": "2",
            "٣": "3",
            "٤": "4",
            "٥": "5",
            "٦": "6",
            "٧": "7",
            "٨": "8",
            "٩": "9",
            "٫": ".",
            "٬": "",
        }
    )

    normalized = (
        text.translate(
            translation
        )
        .strip()
        .lower()
    )

    normalized = re.sub(
        r"[؟?!،,]+",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()
