import os

from dataclasses import dataclass

from dotenv import load_dotenv
from twilio.rest import Client

from app.infrastructure.database.connection import (
    Database,
    get_default_database,
)


load_dotenv()


class OutboundDeliveryUncertain(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class TwilioSendResult:

    inbound_message_sid: str

    twilio_message_sid: str | None

    status: str

    reused: bool


@dataclass(frozen=True)
class TwilioQueuedReply:

    inbound_message_sid: str

    from_address: str

    to_address: str

    body: str

    status: str

    twilio_message_sid: str | None

    media_key: str | None

    media_content_type: str | None


class TwilioSender:

    def __init__(
        self,
        database: Database | None = None,
        account_sid: str | None = None,
        auth_token: str | None = None,
    ):

        self.database = (
            database
            or get_default_database()
        )

        self.account_sid = (
            account_sid
            or os.getenv(
                "TWILIO_ACCOUNT_SID"
            )
        )

        self.auth_token = (
            auth_token
            or os.getenv(
                "TWILIO_AUTH_TOKEN"
            )
        )

        if not self.account_sid:

            raise ValueError(
                "TWILIO_ACCOUNT_SID "
                "is missing."
            )

        if not self.auth_token:

            raise ValueError(
                "TWILIO_AUTH_TOKEN "
                "is missing."
            )

        self.client = Client(
            self.account_sid,
            self.auth_token,
        )

        self._ensure_media_columns()


    # =====================================================
    # DATABASE COMPATIBILITY
    # =====================================================

    def _ensure_media_columns(
        self,
    ) -> None:

        with self.database.session() as conn:

            rows = conn.execute(
                """
                PRAGMA table_info(
                    outbound_messages
                )
                """
            ).fetchall()

            columns = {
                row["name"]
                for row in rows
            }

            if "media_key" not in columns:

                conn.execute(
                    """
                    ALTER TABLE outbound_messages
                    ADD COLUMN media_key TEXT
                    """
                )

            if (
                "media_content_type"
                not in columns
            ):

                conn.execute(
                    """
                    ALTER TABLE outbound_messages
                    ADD COLUMN
                        media_content_type TEXT
                    """
                )


    # =====================================================
    # LOOKUP
    # =====================================================

    def get_queued_reply(
        self,
        *,
        inbound_message_sid: str,
    ) -> TwilioQueuedReply | None:

        inbound_message_sid = (
            inbound_message_sid.strip()
        )

        if not inbound_message_sid:
            raise ValueError(
                "inbound_message_sid "
                "cannot be empty."
            )

        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT
                    inbound_message_sid,
                    from_address,
                    to_address,
                    body,
                    status,
                    twilio_message_sid,
                    media_key,
                    media_content_type
                FROM outbound_messages
                WHERE inbound_message_sid = ?
                LIMIT 1
                """,
                (
                    inbound_message_sid,
                ),
            ).fetchone()

        if row is None:
            return None

        return TwilioQueuedReply(
            inbound_message_sid=(
                row[
                    "inbound_message_sid"
                ]
            ),
            from_address=(
                row["from_address"]
            ),
            to_address=(
                row["to_address"]
            ),
            body=row["body"],
            status=row["status"],
            twilio_message_sid=(
                row[
                    "twilio_message_sid"
                ]
            ),
            media_key=(
                row["media_key"]
            ),
            media_content_type=(
                row[
                    "media_content_type"
                ]
            ),
        )


    # =====================================================
    # QUEUE REPLY
    # =====================================================

    def queue_reply(
        self,
        *,
        inbound_message_sid: str,
        from_address: str,
        to_address: str,
        body: str,
        media_key: str | None = None,
        media_content_type: str | None = None,
    ) -> None:

        inbound_message_sid = (
            inbound_message_sid.strip()
        )

        from_address = (
            from_address.strip()
        )

        to_address = (
            to_address.strip()
        )

        body = (
            body.strip()
        )

        media_key = (
            media_key.strip()
            if media_key
            else None
        )

        media_content_type = (
            media_content_type.strip()
            if media_content_type
            else None
        )


        if not inbound_message_sid:

            raise ValueError(
                "inbound_message_sid "
                "cannot be empty."
            )


        if not from_address:

            raise ValueError(
                "from_address "
                "cannot be empty."
            )


        if not to_address:

            raise ValueError(
                "to_address "
                "cannot be empty."
            )


        if not body:

            raise ValueError(
                "Outbound message body "
                "cannot be empty."
            )


        if (
            media_key
            and not media_content_type
        ):

            raise ValueError(
                "media_content_type is "
                "required with media_key."
            )


        if (
            media_content_type
            and not media_key
        ):

            raise ValueError(
                "media_key is required "
                "with media_content_type."
            )


        with self.database.session() as conn:

            conn.execute(
                """
                INSERT OR IGNORE INTO
                outbound_messages (
                    inbound_message_sid,
                    provider,
                    from_address,
                    to_address,
                    body,
                    status,
                    created_at_utc,
                    media_key,
                    media_content_type
                )
                VALUES (
                    ?,
                    'twilio',
                    ?,
                    ?,
                    ?,
                    'pending',
                    datetime('now'),
                    ?,
                    ?
                )
                """,
                (
                    inbound_message_sid,
                    from_address,
                    to_address,
                    body,
                    media_key,
                    media_content_type,
                ),
            )


            row = conn.execute(
                """
                SELECT
                    from_address,
                    to_address,
                    body,
                    media_key,
                    media_content_type
                FROM outbound_messages
                WHERE inbound_message_sid = ?
                LIMIT 1
                """,
                (
                    inbound_message_sid,
                ),
            ).fetchone()


            if row is None:

                raise RuntimeError(
                    "Outbound message "
                    "could not be created."
                )


            # The same inbound MessageSid must
            # always represent the same reply.
            if (
                row["from_address"]
                != from_address
                or row["to_address"]
                != to_address
                or row["body"]
                != body
                or row["media_key"]
                != media_key
                or row[
                    "media_content_type"
                ]
                != media_content_type
            ):

                raise RuntimeError(
                    "Outbound idempotency "
                    "conflict detected."
                )


    # =====================================================
    # SEND
    # =====================================================

    def send(
        self,
        *,
        inbound_message_sid: str,
        media_url: str | None = None,
    ) -> TwilioSendResult:

        inbound_message_sid = (
            inbound_message_sid.strip()
        )

        media_url = (
            media_url.strip()
            if media_url
            else None
        )


        with self.database.session() as conn:

            row = conn.execute(
                """
                SELECT
                    inbound_message_sid,
                    from_address,
                    to_address,
                    body,
                    status,
                    twilio_message_sid,
                    media_key,
                    media_content_type
                FROM outbound_messages
                WHERE inbound_message_sid = ?
                LIMIT 1
                """,
                (
                    inbound_message_sid,
                ),
            ).fetchone()


            if row is None:

                raise RuntimeError(
                    "Outbound message "
                    "was not queued."
                )


            # ---------------------------------------------
            # ALREADY SENT
            # ---------------------------------------------

            if row["status"] == "sent":

                return TwilioSendResult(
                    inbound_message_sid=(
                        inbound_message_sid
                    ),
                    twilio_message_sid=(
                        row[
                            "twilio_message_sid"
                        ]
                    ),
                    status="sent",
                    reused=True,
                )


            # ---------------------------------------------
            # UNCERTAIN STATE
            #
            # Never blindly POST again.
            #
            # The previous request may already have
            # reached Twilio.
            # ---------------------------------------------

            if row["status"] in {
                "sending",
                "uncertain",
            }:

                raise (
                    OutboundDeliveryUncertain(
                        "Outbound message has "
                        "an uncertain delivery "
                        "state. Automatic resend "
                        "was blocked."
                    )
                )


            if row["status"] != "pending":

                raise RuntimeError(
                    "Unexpected outbound "
                    f"status: {row['status']}"
                )


            media_key = (
                row["media_key"]
            )

            if (
                media_key
                and not media_url
            ):

                raise ValueError(
                    "A fresh media_url is "
                    "required for this "
                    "voice reply."
                )


            if (
                not media_key
                and media_url
            ):

                raise ValueError(
                    "media_url was supplied "
                    "for a text-only reply."
                )


            updated = conn.execute(
                """
                UPDATE outbound_messages

                SET
                    status = 'sending',
                    send_started_at_utc =
                        datetime('now'),
                    last_error = NULL

                WHERE
                    inbound_message_sid = ?
                    AND status = 'pending'
                """,
                (
                    inbound_message_sid,
                ),
            )


            if updated.rowcount != 1:

                raise RuntimeError(
                    "Outbound message could "
                    "not be claimed."
                )


            from_address = (
                row["from_address"]
            )

            to_address = (
                row["to_address"]
            )

            body = (
                row["body"]
            )


        # =================================================
        # TWILIO API
        #
        # This intentionally happens OUTSIDE the SQLite
        # transaction. We never hold a DB lock while making
        # an external network request.
        # =================================================

        try:

            create_kwargs = {
                "from_": from_address,
                "to": to_address,
            }

            if media_key:

                create_kwargs[
                    "media_url"
                ] = [
                    media_url
                ]

            else:

                create_kwargs[
                    "body"
                ] = body


            message = (
                self.client.messages.create(
                    **create_kwargs
                )
            )

        except Exception as exc:

            # We cannot safely know whether the request
            # reached Twilio before the failure occurred.
            #
            # Therefore we do NOT automatically resend.
            with self.database.session() as conn:

                conn.execute(
                    """
                    UPDATE outbound_messages

                    SET
                        status = 'uncertain',
                        last_error = ?

                    WHERE inbound_message_sid = ?
                    """,
                    (
                        repr(exc),
                        inbound_message_sid,
                    ),
                )

            raise


        twilio_message_sid = (
            message.sid
        )


        # =================================================
        # MARK SENT
        # =================================================

        with self.database.session() as conn:

            conn.execute(
                """
                UPDATE outbound_messages

                SET
                    status = 'sent',
                    twilio_message_sid = ?,
                    sent_at_utc =
                        datetime('now'),
                    last_error = NULL

                WHERE inbound_message_sid = ?
                """,
                (
                    twilio_message_sid,
                    inbound_message_sid,
                ),
            )


        return TwilioSendResult(
            inbound_message_sid=(
                inbound_message_sid
            ),

            twilio_message_sid=(
                twilio_message_sid
            ),

            status="sent",

            reused=False,
        )
