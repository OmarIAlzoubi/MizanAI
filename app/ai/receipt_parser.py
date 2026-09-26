from __future__ import annotations

import base64
import mimetypes
import os

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field


load_dotenv()


class ReceiptParseError(RuntimeError):
    pass


class ReceiptData(BaseModel):

    is_receipt: bool

    merchant: str | None = None

    total_amount: float | None = Field(
        default=None,
        ge=0,
    )

    currency: str | None = None

    transaction_date: str | None = None

    receipt_number: str | None = None

    confidence: float = Field(
        ge=0,
        le=1,
    )

    notes: str | None = None


class ReceiptParser:

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "grok-4.7",
    ):

        api_key = (
            api_key
            or os.getenv("XAI_API_KEY")
        )

        if not api_key:
            raise ReceiptParseError(
                "XAI_API_KEY was not found."
            )

        self.model = model

        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )

    def parse(
        self,
        image_path: str | Path,
    ) -> ReceiptData:

        image_path = Path(
            image_path
        )

        if not image_path.exists():
            raise ReceiptParseError(
                f"Image does not exist: "
                f"{image_path}"
            )

        mime_type = (
            mimetypes.guess_type(
                image_path.name
            )[0]
            or ""
        )

        if mime_type not in {
            "image/jpeg",
            "image/png",
        }:
            raise ReceiptParseError(
                "Receipt image must be "
                "JPEG or PNG."
            )

        image_bytes = (
            image_path.read_bytes()
        )

        if len(image_bytes) > (
            20 * 1024 * 1024
        ):
            raise ReceiptParseError(
                "Image exceeds 20 MiB."
            )

        encoded = base64.b64encode(
            image_bytes
        ).decode("ascii")

        data_url = (
            f"data:{mime_type};"
            f"base64,{encoded}"
        )

        completion = (
            self.client.beta.chat
            .completions.parse(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are the receipt extraction "
                            "component of MizanAI, a personal "
                            "finance assistant.\n\n"

                            "Extract only information visibly "
                            "supported by the receipt image.\n\n"

                            "Rules:\n"
                            "- Never invent missing values.\n"
                            "- total_amount must be the final "
                            "amount actually paid or due, not "
                            "subtotal or VAT alone.\n"
                            "- For Saudi receipts, currency "
                            "should normally be SAR only when "
                            "the image supports that conclusion.\n"
                            "- transaction_date should use "
                            "YYYY-MM-DD when a date is clearly "
                            "visible and unambiguous.\n"
                            "- merchant should be the business "
                            "or store name, not a bank/payment "
                            "processor unless that is actually "
                            "the merchant.\n"
                            "- If the image is not a receipt, "
                            "set is_receipt=false.\n"
                            "- confidence describes confidence "
                            "in the extracted transaction facts.\n"
                            "- Do not infer a spending category."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Analyze this receipt and "
                                    "extract its transaction data."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": data_url,
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                response_format=ReceiptData,
            )
        )

        parsed = (
            completion
            .choices[0]
            .message
            .parsed
        )

        if parsed is None:
            raise ReceiptParseError(
                "Grok returned no parsed "
                "receipt result."
            )

        return parsed