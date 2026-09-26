import json
import os
import re

from pathlib import Path

import boto3

from dotenv import load_dotenv

from app.ai.grok_voice import (
    GrokVoice,
)

from app.ai.receipt_parser import (
    ReceiptParser,
)

from app.application.chat_orchestrator import (
    ChatOrchestrator,
)

from app.application.receipt_demo_flow import (
    PendingReceiptStore,
    build_transaction_message,
    format_partial_confirmation,
    format_receipt_confirmation,
    interpret_receipt_followup,
)

from app.core.execution_context import (
    external_message_context,
)

from app.infrastructure.database.connection import (
    get_default_database,
)

from app.infrastructure.database.schema import (
    initialize_database,
)

from app.infrastructure.messaging.twilio_media import (
    TwilioMediaDownloader,
    find_first_audio_media,
    find_first_image_media,
)

from app.infrastructure.messaging.twilio_sender import (
    OutboundDeliveryUncertain,
    TwilioSender,
)

from app.infrastructure.messaging.voice_media_store import (
    VoiceMediaStore,
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()


QUEUE_URL = os.getenv(
    "MIZAN_SQS_QUEUE_URL"
)

AWS_REGION = os.getenv(
    "AWS_REGION",
    "eu-central-1",
)

AWS_PROFILE = os.getenv(
    "AWS_PROFILE",
    "mizanai-worker",
)


if not QUEUE_URL:
    raise ValueError(
        "MIZAN_SQS_QUEUE_URL is missing."
    )


# =========================================================
# AWS
# =========================================================

session = boto3.Session(
    profile_name=AWS_PROFILE,
    region_name=AWS_REGION,
)

sqs = session.client(
    "sqs"
)


# =========================================================
# APPLICATION SERVICES
# =========================================================

initialize_database()

database = get_default_database()

orchestrator = ChatOrchestrator()

twilio_sender = TwilioSender()

twilio_media = TwilioMediaDownloader()

grok_voice = GrokVoice()

voice_media_store = VoiceMediaStore()

receipt_parser = ReceiptParser()

pending_receipts = PendingReceiptStore()


# =========================================================
# VOICE HELPERS
# =========================================================

def is_voice_message(
    payload: dict,
) -> bool:

    return (
        find_first_audio_media(
            payload
        )
        is not None
    )


def clean_tts_text(
    text: str,
) -> str:

    cleaned = re.sub(
        r"[*_`#]",
        "",
        text,
    )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    return cleaned.strip()


def detect_tts_language(
    text: str,
) -> str:

    if re.search(
        r"[\u0600-\u06FF]",
        text,
    ):
        return "ar-SA"

    return "en-US"


def transcribe_voice_message(
    *,
    payload: dict,
    message_sid: str,
) -> str:

    item = find_first_audio_media(
        payload
    )

    if item is None:
        raise ValueError(
            "Incoming message "
            "contains no audio media."
        )


    print()
    print(
        "[Voice In]"
    )

    print(
        "Content-Type:",
        item.content_type,
    )

    downloaded = (
        twilio_media.download_audio(
            item=item,
            message_sid=message_sid,
        )
    )


    try:

        transcription = (
            grok_voice.transcribe(
                audio_path=(
                    downloaded.path
                )
            )
        )

    finally:

        downloaded.path.unlink(
            missing_ok=True
        )


    transcript = (
        transcription.text
        or ""
    ).strip()


    if not transcript:

        raise RuntimeError(
            "Grok STT returned "
            "an empty transcript."
        )


    print()
    print(
        "[Grok STT]"
    )

    print(
        "Language:",
        transcription.language,
    )

    print(
        "Transcript:",
        transcript,
    )


    return transcript


# =========================================================
# RECEIPT DEMO
# =========================================================

def process_receipt_image(
    *,
    payload: dict,
    message_sid: str,
    user_address: str,
) -> str:

    image_item = (
        find_first_image_media(
            payload
        )
    )

    if image_item is None:
        raise ValueError(
            "Incoming message has "
            "no image media."
        )


    print()
    print(
        "[Receipt Image]"
    )

    print(
        "Content-Type:",
        image_item.content_type,
    )


    downloaded = (
        twilio_media.download_image(
            item=image_item,
            message_sid=message_sid,
        )
    )


    try:

        parsed = (
            receipt_parser.parse(
                downloaded.path
            )
        )

    finally:

        downloaded.path.unlink(
            missing_ok=True
        )


    print()
    print(
        "[Receipt Parser]"
    )

    print(
        json.dumps(
            parsed.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
    )


    if not parsed.is_receipt:

        return (
            "ما قدرت أتعرف على الصورة "
            "كفاتورة واضحة."
        )


    if parsed.confidence < 0.75:

        return (
            "قرأت الصورة كفاتورة، "
            "لكن ثقتي بالبيانات منخفضة. "
            "جرّب صورة أوضح."
        )


    if (
        parsed.total_amount is None
        or not parsed.merchant
        or not parsed.currency
    ):

        return (
            "عرفت أنها فاتورة، "
            "لكن ما قدرت أقرأ التاجر "
            "والمبلغ والعملة بشكل واضح."
        )


    pending = (
        pending_receipts.put(
            user_key=user_address,
            receipt=parsed,
        )
    )


    return format_receipt_confirmation(
        pending
    )


def maybe_handle_pending_receipt(
    *,
    user_address: str,
    user_message: str,
    message_sid: str,
) -> tuple[bool, str | None]:

    pending = (
        pending_receipts.get(
            user_address
        )
    )

    if pending is None:

        return (
            False,
            None,
        )


    decision = (
        interpret_receipt_followup(
            text=user_message,
            receipt=pending,
        )
    )


    if decision.kind == "none":

        return (
            False,
            None,
        )


    if decision.kind == "cancel":

        pending_receipts.clear(
            user_address
        )

        return (
            True,
            "تمام، ألغيت تسجيل الفاتورة.",
        )


    if decision.kind == "invalid":

        return (
            True,
            decision.reason
            or (
                "ما قدرت أحدد المبلغ "
                "من ردك."
            ),
        )


    if decision.amount is None:

        raise RuntimeError(
            "Receipt decision has "
            "no amount."
        )


    synthetic_message = (
        build_transaction_message(
            receipt=pending,
            amount=decision.amount,
        )
    )


    print()
    print(
        "[Receipt Confirmation]"
    )

    print(
        "User reply:",
        user_message,
    )

    print(
        "Resolved transaction:",
        synthetic_message,
    )


    # Use the EXISTING MizanAI transaction pipeline.
    # This keeps transaction validation, semantics,
    # and MessageSid idempotency in one place.
    with external_message_context(
        message_sid
    ):

        result = (
            orchestrator.handle(
                synthetic_message
            )
        )


    if (
        not result.reply
        or not result.reply.strip()
    ):

        raise RuntimeError(
            "MizanAI returned an empty "
            "receipt confirmation reply."
        )


    # Clear only AFTER the existing pipeline
    # completed successfully.
    pending_receipts.clear(
        user_address
    )


    if decision.kind == "partial":

        return (
            True,
            format_partial_confirmation(
                receipt=pending,
                amount=decision.amount,
            ),
        )


    return (
        True,
        result.reply.strip(),
    )


# =========================================================
# PROCESSED MESSAGE LEDGER
# =========================================================

def get_processed_reply(
    message_sid: str,
) -> str | None:

    with database.session() as conn:

        row = conn.execute(
            """
            SELECT
                reply
            FROM processed_inbound_messages
            WHERE message_sid = ?
            LIMIT 1
            """,
            (
                message_sid,
            ),
        ).fetchone()


    if row is None:
        return None


    return row[
        "reply"
    ]


def mark_message_processed(
    *,
    message_sid: str,
    source: str,
    reply: str,
) -> str:

    with database.session() as conn:

        conn.execute(
            """
            INSERT OR IGNORE INTO
            processed_inbound_messages (
                message_sid,
                source,
                processed_at_utc,
                reply
            )
            VALUES (
                ?,
                ?,
                datetime('now'),
                ?
            )
            """,
            (
                message_sid,
                source,
                reply,
            ),
        )


        row = conn.execute(
            """
            SELECT
                reply
            FROM processed_inbound_messages
            WHERE message_sid = ?
            LIMIT 1
            """,
            (
                message_sid,
            ),
        ).fetchone()


    if row is None:

        raise RuntimeError(
            "Processed inbound message "
            "could not be persisted."
        )


    persisted_reply = (
        row["reply"]
    )


    if not persisted_reply:

        raise RuntimeError(
            "Processed inbound message "
            "has no persisted reply."
        )


    return persisted_reply


# =========================================================
# MIZANAI PROCESSING
# =========================================================

def process_message(
    payload: dict,
) -> str:

    message_sid = (
        payload.get(
            "message_sid"
        )
        or ""
    ).strip()


    user_address = (
        payload.get(
            "from"
        )
        or ""
    ).strip()


    if not message_sid:

        raise ValueError(
            "Incoming message "
            "has no message_sid."
        )


    if not user_address:

        raise ValueError(
            "Incoming message "
            "has no From address."
        )


    # -----------------------------------------------------
    # RECEIPT IMAGE
    # -----------------------------------------------------

    image_item = (
        find_first_image_media(
            payload
        )
    )

    if image_item is not None:

        reply = (
            process_receipt_image(
                payload=payload,
                message_sid=message_sid,
                user_address=user_address,
            )
        )

        print()
        print(
            "=" * 40
        )

        print(
            "MizanAI reply"
        )

        print(
            "=" * 40
        )

        print(
            reply
        )

        print()
        print(
            "Route: receipt_demo"
        )

        print(
            "Source: grok_receipt_parser"
        )

        return reply


    # -----------------------------------------------------
    # VOICE OR TEXT INPUT
    # -----------------------------------------------------

    audio_item = (
        find_first_audio_media(
            payload
        )
    )


    if audio_item is not None:

        user_message = (
            transcribe_voice_message(
                payload=payload,
                message_sid=message_sid,
            )
        )

    else:

        user_message = (
            payload.get(
                "body"
            )
            or ""
        ).strip()


    if not user_message:

        raise ValueError(
            "Incoming message has "
            "no supported text, audio, "
            "or receipt image."
        )


    print()
    print(
        f"User: {user_message}"
    )


    # -----------------------------------------------------
    # PENDING RECEIPT FOLLOW-UP
    # -----------------------------------------------------

    handled, receipt_reply = (
        maybe_handle_pending_receipt(
            user_address=user_address,
            user_message=user_message,
            message_sid=message_sid,
        )
    )


    if handled:

        if not receipt_reply:
            raise RuntimeError(
                "Receipt flow returned "
                "an empty reply."
            )

        print()
        print(
            "=" * 40
        )

        print(
            "MizanAI reply"
        )

        print(
            "=" * 40
        )

        print(
            receipt_reply
        )

        print()
        print(
            "Route: receipt_demo"
        )

        print(
            "Source: receipt_confirmation"
        )

        return receipt_reply


    # -----------------------------------------------------
    # NORMAL MIZANAI
    # -----------------------------------------------------

    # MessageSid is execution metadata.
    # It is NOT added to the LLM prompt.
    with external_message_context(
        message_sid
    ):

        result = (
            orchestrator.handle(
                user_message
            )
        )


    reply = (
        result.reply
        or ""
    ).strip()


    if not reply:

        raise RuntimeError(
            "MizanAI returned "
            "an empty reply."
        )


    print()
    print(
        "=" * 40
    )

    print(
        "MizanAI reply"
    )

    print(
        "=" * 40
    )

    print(
        reply
    )


    print()
    print(
        "Route:",
        result.route,
    )

    print(
        "Source:",
        result.response_source,
    )


    return reply


# =========================================================
# VOICE OUTBOUND
# =========================================================

def ensure_voice_reply_queued(
    *,
    message_sid: str,
    from_address: str,
    to_address: str,
    reply: str,
) -> str:

    queued = (
        twilio_sender.get_queued_reply(
            inbound_message_sid=(
                message_sid
            )
        )
    )


    if queued is not None:

        if not queued.media_key:

            raise RuntimeError(
                "Outbound idempotency "
                "conflict: this inbound "
                "message was previously "
                "queued as text."
            )

        twilio_sender.queue_reply(
            inbound_message_sid=(
                message_sid
            ),
            from_address=(
                from_address
            ),
            to_address=(
                to_address
            ),
            body=reply,
            media_key=(
                queued.media_key
            ),
            media_content_type=(
                queued.media_content_type
                or "audio/mpeg"
            ),
        )

        return queued.media_key


    tts_text = (
        clean_tts_text(
            reply
        )
    )


    if not tts_text:

        raise RuntimeError(
            "Reply became empty after "
            "TTS text cleanup."
        )


    output_dir = Path(
        "tmp/outbound_voice"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{message_sid}.mp3"
    )


    try:

        grok_voice.synthesize(
            text=tts_text,
            output_path=(
                output_path
            ),
            language=(
                detect_tts_language(
                    tts_text
                )
            ),
        )


        media_key = (
            voice_media_store.upload_audio(
                file_path=(
                    output_path
                ),
                content_type=(
                    "audio/mpeg"
                ),
            )
        )


        twilio_sender.queue_reply(
            inbound_message_sid=(
                message_sid
            ),
            from_address=(
                from_address
            ),
            to_address=(
                to_address
            ),
            body=reply,
            media_key=(
                media_key
            ),
            media_content_type=(
                "audio/mpeg"
            ),
        )


        return media_key


    finally:

        output_path.unlink(
            missing_ok=True
        )


# =========================================================
# OUTBOUND DELIVERY
# =========================================================

def deliver_reply(
    *,
    payload: dict,
    reply: str,
) -> None:

    message_sid = (
        payload.get(
            "message_sid"
        )
        or ""
    ).strip()


    user_address = (
        payload.get(
            "from"
        )
        or ""
    ).strip()


    twilio_address = (
        payload.get(
            "to"
        )
        or ""
    ).strip()


    if not user_address:

        raise ValueError(
            "Incoming message "
            "has no From address."
        )


    if not twilio_address:

        raise ValueError(
            "Incoming message "
            "has no To address."
        )


    # For an inbound WhatsApp message:
    #
    # payload["from"] = user
    # payload["to"]   = Twilio
    #
    # Outbound reply reverses them.

    if is_voice_message(
        payload
    ):

        media_key = (
            ensure_voice_reply_queued(
                message_sid=(
                    message_sid
                ),
                from_address=(
                    twilio_address
                ),
                to_address=(
                    user_address
                ),
                reply=reply,
            )
        )


        media_url = (
            voice_media_store
            .create_presigned_url(
                key=media_key,
                expires_in=3600,
            )
        )


        send_result = (
            twilio_sender.send(
                inbound_message_sid=(
                    message_sid
                ),
                media_url=(
                    media_url
                ),
            )
        )

        delivery_mode = "voice"


    else:

        twilio_sender.queue_reply(
            inbound_message_sid=(
                message_sid
            ),

            from_address=(
                twilio_address
            ),

            to_address=(
                user_address
            ),

            body=reply,
        )


        send_result = (
            twilio_sender.send(
                inbound_message_sid=(
                    message_sid
                )
            )
        )

        delivery_mode = "text"


    print()
    print(
        "[Twilio Outbound]"
    )

    print(
        "Mode:",
        delivery_mode,
    )

    print(
        "Status:",
        send_result.status,
    )

    print(
        "Message SID:",
        send_result.twilio_message_sid,
    )

    print(
        "Reused:",
        send_result.reused,
    )


# =========================================================
# WORKER
# =========================================================

def run():

    print(
        "MizanAI SQS worker started."
    )

    print(
        f"Region: {AWS_REGION}"
    )

    print(
        f"AWS profile: {AWS_PROFILE}"
    )


    while True:

        response = (
            sqs.receive_message(
                QueueUrl=QUEUE_URL,

                MaxNumberOfMessages=1,

                WaitTimeSeconds=20,

                VisibilityTimeout=180,

                MessageAttributeNames=[
                    "All"
                ],
            )
        )


        messages = (
            response.get(
                "Messages",
                [],
            )
        )


        for message in messages:

            receipt_handle = (
                message[
                    "ReceiptHandle"
                ]
            )


            try:

                payload = json.loads(
                    message[
                        "Body"
                    ]
                )


                print()
                print(
                    "=" * 40
                )

                print(
                    "Incoming MizanAI message"
                )

                print(
                    "=" * 40
                )

                print(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        indent=2,
                    )
                )


                message_sid = (
                    payload.get(
                        "message_sid"
                    )
                    or ""
                ).strip()


                if not message_sid:

                    raise ValueError(
                        "Incoming message "
                        "has no message_sid."
                    )


                # =========================================
                # BUSINESS PROCESSING
                # =========================================
                #
                # If MizanAI already processed this
                # MessageSid, DO NOT run the LLM/financial
                # pipeline again.
                #
                # Instead reuse the exact persisted reply.
                # =========================================

                existing_reply = (
                    get_processed_reply(
                        message_sid
                    )
                )


                if existing_reply:

                    print()
                    print(
                        "[Inbound Idempotency] "
                        "Business processing "
                        "already completed."
                    )

                    print(
                        "Reusing persisted reply."
                    )

                    reply = (
                        existing_reply
                    )


                else:

                    reply = (
                        process_message(
                            payload
                        )
                    )


                    # Persist the reply BEFORE outbound
                    # delivery.
                    #
                    # If the process crashes after this
                    # point, a retry can use the exact
                    # same reply without calling the LLM
                    # again.

                    reply = (
                        mark_message_processed(
                            message_sid=(
                                message_sid
                            ),

                            source=(
                                payload.get(
                                    "source"
                                )
                                or "unknown"
                            ),

                            reply=reply,
                        )
                    )


                # =========================================
                # OUTBOUND WHATSAPP
                # =========================================

                deliver_reply(
                    payload=payload,
                    reply=reply,
                )


                # =========================================
                # ACKNOWLEDGE SQS
                #
                # Delete only after:
                #
                # 1. business processing completed
                # 2. reply persisted
                # 3. outbound delivery recorded as sent
                # =========================================

                sqs.delete_message(
                    QueueUrl=QUEUE_URL,
                    ReceiptHandle=(
                        receipt_handle
                    ),
                )


                print()
                print(
                    "Message processed, "
                    "reply sent, and "
                    "deleted from SQS."
                )


            except (
                OutboundDeliveryUncertain
            ) as error:

                print()
                print(
                    "Outbound delivery "
                    "state is uncertain:"
                )

                print(
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                print(
                    "Message was NOT deleted."
                )

                print(
                    "Automatic resend was "
                    "blocked to avoid a "
                    "duplicate WhatsApp reply."
                )


            except Exception as error:

                print()
                print(
                    "Processing failed:"
                )

                print(
                    f"{type(error).__name__}: "
                    f"{error}"
                )

                print(
                    "Message was NOT deleted. "
                    "SQS will retry it."
                )


if __name__ == "__main__":
    run()
