from __future__ import annotations

import getpass
import json
import os
import sqlite3
import sys

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(
    __file__
).resolve().parent

ENV_PATH = (
    ROOT
    / ".env"
)

CONFIG_DIR = (
    ROOT
    / "config"
)

CONFIG_PATH = (
    CONFIG_DIR
    / "mizanai.json"
)


def main() -> None:

    _banner()

    _check_python()

    env = _read_env(
        ENV_PATH
    )

    print(
        "\n1) How would you like "
        "to run MizanAI?\n"
    )

    print(
        "   [1] Local App\n"
        "       Dashboard + AI on "
        "this computer.\n"
        "       No AWS/Twilio required.\n"
    )

    print(
        "   [2] AWS + WhatsApp\n"
        "       Full WhatsApp experience "
        "with the cloud messaging path.\n"
    )

    mode_choice = _choose(
        "Choose",
        {
            "1": "local",
            "2": "aws_whatsapp",
        },
    )

    mode = mode_choice

    env[
        "MIZAN_MODE"
    ] = mode

    print(
        "\n2) AI configuration\n"
    )

    _ensure_secret(
        env,
        "XAI_API_KEY",
        (
            "xAI API key "
            "(input is hidden)"
        ),
    )

    if not env.get(
        "XAI_MODEL"
    ):
        env[
            "XAI_MODEL"
        ] = "grok-4.7"

    if mode == "aws_whatsapp":

        print(
            "\n3) WhatsApp + AWS "
            "configuration\n"
        )

        _ensure_value(
            env,
            "TWILIO_ACCOUNT_SID",
            "Twilio Account SID",
        )

        _ensure_secret(
            env,
            "TWILIO_AUTH_TOKEN",
            (
                "Twilio Auth Token "
                "(input is hidden)"
            ),
        )

        _ensure_value(
            env,
            "AWS_REGION",
            "AWS region",
            default=(
                env.get(
                    "AWS_REGION"
                )
                or "eu-central-1"
            ),
        )

        _ensure_value(
            env,
            "AWS_PROFILE",
            "AWS CLI profile",
            default=(
                env.get(
                    "AWS_PROFILE"
                )
                or "mizanai-worker"
            ),
        )

        _ensure_value(
            env,
            "MIZAN_SQS_QUEUE_URL",
            "Inbound SQS FIFO URL",
        )

        _ensure_value(
            env,
            "MIZAN_VOICE_BUCKET",
            "Voice S3 bucket name",
        )

    _write_env(
        ENV_PATH,
        env,
    )

    # Imports happen only after .env exists.
    from app.infrastructure.database.connection import (
        DEFAULT_DATABASE_PATH,
        get_default_database,
    )

    from app.infrastructure.database.schema import (
        initialize_database,
    )

    database = (
        get_default_database()
    )

    initialize_database(
        database
    )

    existing_count = (
        _transaction_count(
            database
        )
    )

    if existing_count:

        print(
            "\nExisting MizanAI data detected:"
        )

        print(
            f"   {existing_count} transactions"
        )

        print(
            "\nFor safety, setup will not "
            "overwrite it automatically."
        )

        print(
            "\n   [1] Keep existing data "
            "(recommended)"
        )

        print(
            "   [2] Back it up and start "
            "with new onboarding data"
        )

        existing_choice = _choose(
            "Choose",
            {
                "1": "existing",
                "2": "reset",
            },
        )

        if existing_choice == "existing":

            data_mode = "existing"

            _save_config(
                mode=mode,
                data_mode=data_mode,
            )

            _finish(
                mode=mode,
                data_mode=data_mode,
            )

            return

        backup_path = (
            _backup_and_reset_database(
                DEFAULT_DATABASE_PATH
            )
        )

        print(
            "\nBackup created:"
        )

        print(
            f"   {backup_path}"
        )

        # Re-create a clean DB.
        initialize_database(
            database
        )

    print(
        "\n4) How would you like "
        "to start?\n"
    )

    print(
        "   [1] Start from scratch\n"
        "       Enter your current balance "
        "and build history naturally.\n"
    )

    print(
        "   [2] Import a bank statement\n"
        "       Bootstrap transaction history "
        "from a statement.\n"
        "       Current adapter: "
        "Al Rajhi PDF.\n"
    )

    print(
        "   [3] Demo data\n"
        "       Synthetic transactions for "
        "an instant demo.\n"
    )

    data_mode = _choose(
        "Choose",
        {
            "1": "fresh",
            "2": "statement",
            "3": "demo",
        },
    )

    if data_mode == "fresh":

        _setup_fresh(
            database
        )

    elif data_mode == "statement":

        _setup_statement(
            database
        )

    elif data_mode == "demo":

        _setup_demo(
            database
        )

    _save_config(
        mode=mode,
        data_mode=data_mode,
    )

    _finish(
        mode=mode,
        data_mode=data_mode,
    )


def _setup_fresh(
    database,
) -> None:

    from app.onboarding.demo_seed import (
        set_fresh_balance,
    )

    print(
        "\nStarting from scratch"
    )

    balance = (
        _ask_money(
            "Current balance (SAR)"
        )
    )

    minor = int(
        (
            balance
            * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    set_fresh_balance(
        database=database,
        balance_minor=minor,
    )

    print(
        "\n✓ Empty ledger created"
    )

    print(
        f"✓ Current balance: "
        f"{balance:.2f} SAR"
    )


def _setup_demo(
    database,
) -> None:

    from app.onboarding.demo_seed import (
        seed_demo_data,
    )

    count = seed_demo_data(
        database=database
    )

    print(
        "\n✓ Demo account created"
    )

    print(
        f"✓ {count} synthetic "
        "transactions loaded"
    )

    print(
        "✓ Current demo balance: "
        "8,450.00 SAR"
    )


def _setup_statement(
    database,
) -> None:

    from app.onboarding.alrajhi_statement import (
        import_statement,
        parse_alrajhi_pdf,
    )

    print(
        "\nBank statement import"
    )

    print(
        "Current built-in adapter: "
        "Al Rajhi PDF"
    )

    while True:

        raw_path = input(
            "\nStatement PDF path: "
        ).strip().strip(
            '"'
        )

        path = Path(
            raw_path
        ).expanduser()

        if path.exists():
            break

        print(
            "File not found. "
            "Try again."
        )

    print(
        "\nReading and validating "
        "the statement..."
    )

    preview = (
        parse_alrajhi_pdf(
            path
        )
    )

    print(
        "\nStatement preview"
    )

    print(
        "------------------------------"
    )

    print(
        f"Period: "
        f"{preview.period_start} → "
        f"{preview.period_end}"
    )

    print(
        f"Transactions: "
        f"{len(preview.transactions)}"
    )

    print(
        f"Withdrawals: "
        f"{preview.withdrawal_count} "
        f"({preview.withdrawal_total:.2f} SAR)"
    )

    print(
        f"Deposits: "
        f"{preview.deposit_count} "
        f"({preview.deposit_total:.2f} SAR)"
    )

    print(
        f"Opening balance: "
        f"{preview.opening_balance:.2f} SAR"
    )

    print(
        f"Closing balance: "
        f"{preview.closing_balance:.2f} SAR"
    )

    print(
        "\nIntegrity checks: ✓"
    )

    print(
        "\nSample transactions:"
    )

    for tx in (
        preview.transactions[:5]
    ):

        print(
            "  - "
            f"{tx.occurred_at_utc.date()} | "
            f"{tx.direction:<6} | "
            f"{tx.amount:>8.2f} SAR | "
            f"{tx.merchant or 'Unknown'}"
        )

    confirm = input(
        "\nImport this statement? "
        "[Y/n]: "
    ).strip().lower()

    if confirm not in {
        "",
        "y",
        "yes",
    }:
        print(
            "\nImport cancelled."
        )
        raise SystemExit(
            0
        )

    count = import_statement(
        preview=preview,
        database=database,
    )

    print(
        f"\n✓ Imported {count} "
        "transactions"
    )

    print(
        "✓ Closing balance set as "
        "the verified balance anchor"
    )

    print(
        "✓ Account number / IBAN were "
        "not stored by MizanAI"
    )


def _save_config(
    *,
    mode: str,
    data_mode: str,
) -> None:

    CONFIG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "version": 1,
        "mode": mode,
        "data_mode": data_mode,
        "currency": "SAR",
        "timezone": "Asia/Riyadh",
        "voice_enabled": True,
        "receipt_enabled": True,
        "whatsapp_enabled": (
            mode
            == "aws_whatsapp"
        ),
    }

    CONFIG_PATH.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _backup_and_reset_database(
    database_path: Path,
) -> Path:

    timestamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_path = (
        database_path.with_name(
            f"{database_path.stem}"
            f".backup-{timestamp}"
            f"{database_path.suffix}"
        )
    )

    if database_path.exists():

        source = sqlite3.connect(
            database_path
        )

        destination = sqlite3.connect(
            backup_path
        )

        try:

            source.backup(
                destination
            )

        finally:

            destination.close()
            source.close()

    for suffix in (
        "",
        "-wal",
        "-shm",
    ):

        target = Path(
            str(database_path)
            + suffix
        )

        if target.exists():
            target.unlink()

    return backup_path


def _transaction_count(
    database,
) -> int:

    with database.session() as conn:

        return int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM transactions
                """
            )
            .fetchone()[0]
        )


def _finish(
    *,
    mode: str,
    data_mode: str,
) -> None:

    print(
        "\n"
        + "=" * 52
    )

    print(
        "MizanAI setup complete ✓"
    )

    print(
        "=" * 52
    )

    print(
        f"Mode: {mode}"
    )

    print(
        f"Data: {data_mode}"
    )

    print(
        "\nRun MizanAI with:"
    )

    print(
        "\n    python run.py\n"
    )


def _banner() -> None:

    print(
        "\n"
        "╭──────────────────────────────╮\n"
        "│       Welcome to MizanAI     │\n"
        "╰──────────────────────────────╯"
    )

    print(
        "\nFirst-run setup takes only "
        "a couple of minutes."
    )


def _check_python() -> None:

    if sys.version_info < (
        3,
        11,
    ):
        raise SystemExit(
            "MizanAI requires "
            "Python 3.11+."
        )


def _choose(
    prompt: str,
    options: dict[str, str],
) -> str:

    while True:

        value = input(
            f"{prompt}: "
        ).strip()

        if value in options:
            return options[
                value
            ]

        print(
            "Please choose one of: "
            + ", ".join(
                options
            )
        )


def _ask_money(
    prompt: str,
) -> Decimal:

    while True:

        value = input(
            f"{prompt}: "
        ).strip()

        value = value.replace(
            ",",
            "",
        )

        try:

            amount = Decimal(
                value
            )

            if amount < 0:
                raise ValueError

            return amount.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        except (
            InvalidOperation,
            ValueError,
        ):

            print(
                "Enter a valid non-negative "
                "amount, e.g. 5451.51"
            )


def _ensure_value(
    env: dict[str, str],
    key: str,
    label: str,
    *,
    default: str | None = None,
) -> None:

    current = (
        env.get(
            key,
            ""
        ).strip()
    )

    if current:
        print(
            f"✓ {label} already configured"
        )
        return

    while True:

        suffix = (
            f" [{default}]"
            if default
            else ""
        )

        value = input(
            f"{label}{suffix}: "
        ).strip()

        if (
            not value
            and default
        ):
            value = default

        if value:
            env[
                key
            ] = value
            return

        print(
            "This value is required."
        )


def _ensure_secret(
    env: dict[str, str],
    key: str,
    label: str,
) -> None:

    current = (
        env.get(
            key,
            ""
        ).strip()
    )

    if current:
        print(
            f"✓ {key} already configured"
        )
        return

    while True:

        value = getpass.getpass(
            f"{label}: "
        ).strip()

        if value:
            env[
                key
            ] = value
            return

        print(
            "This value is required."
        )


def _read_env(
    path: Path,
) -> dict[str, str]:

    values = {}

    if not path.exists():
        return values

    for raw_line in (
        path.read_text(
            encoding="utf-8"
        ).splitlines()
    ):

        line = raw_line.strip()

        if (
            not line
            or line.startswith(
                "#"
            )
            or "=" not in line
        ):
            continue

        key, value = (
            line.split(
                "=",
                1,
            )
        )

        values[
            key.strip()
        ] = value.strip()

    return values


def _write_env(
    path: Path,
    env: dict[str, str],
) -> None:

    ordered_keys = [
        "XAI_API_KEY",
        "XAI_MODEL",
        "MIZAN_MODE",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "AWS_REGION",
        "AWS_PROFILE",
        "MIZAN_SQS_QUEUE_URL",
        "MIZAN_VOICE_BUCKET",
    ]

    lines = [
        "# Generated by MizanAI setup.py",
        "",
    ]

    emitted = set()

    for key in ordered_keys:

        if key in env:

            lines.append(
                f"{key}={env[key]}"
            )

            emitted.add(
                key
            )

    for key in sorted(
        env
    ):

        if key in emitted:
            continue

        lines.append(
            f"{key}={env[key]}"
        )

    lines.append(
        ""
    )

    path.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
