from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from dotenv import load_dotenv


load_dotenv()


class TwilioMediaError(RuntimeError):
    pass


@dataclass(frozen=True)
class TwilioMediaItem:
    url: str
    content_type: str


@dataclass(frozen=True)
class DownloadedTwilioMedia:
    path: Path
    content_type: str


def _find_first_media(
    payload: dict,
    *,
    prefix: str,
) -> TwilioMediaItem | None:

    media_items = (
        payload.get("media")
        or []
    )

    if not isinstance(
        media_items,
        list,
    ):
        return None

    for item in media_items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        url = (
            item.get("url")
            or item.get("media_url")
            or item.get("MediaUrl")
            or ""
        )

        content_type = (
            item.get("content_type")
            or item.get("media_content_type")
            or item.get("type")
            or item.get("MediaContentType")
            or ""
        )

        url = str(url).strip()

        content_type = (
            str(content_type)
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        if (
            url
            and content_type.startswith(
                prefix
            )
        ):
            return TwilioMediaItem(
                url=url,
                content_type=content_type,
            )

    return None


def find_first_audio_media(
    payload: dict,
) -> TwilioMediaItem | None:

    return _find_first_media(
        payload,
        prefix="audio/",
    )


def find_first_image_media(
    payload: dict,
) -> TwilioMediaItem | None:

    return _find_first_media(
        payload,
        prefix="image/",
    )


class TwilioMediaDownloader:

    def __init__(
        self,
        *,
        account_sid: str | None = None,
        auth_token: str | None = None,
        max_bytes: int = 20 * 1024 * 1024,
        timeout_seconds: int = 60,
    ):

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

        self.max_bytes = max_bytes

        self.timeout_seconds = (
            timeout_seconds
        )

        if not self.account_sid:
            raise TwilioMediaError(
                "TWILIO_ACCOUNT_SID "
                "is missing."
            )

        if not self.auth_token:
            raise TwilioMediaError(
                "TWILIO_AUTH_TOKEN "
                "is missing."
            )

    def download_audio(
        self,
        *,
        item: TwilioMediaItem,
        message_sid: str,
        output_dir: str | Path = (
            "tmp/inbound_voice"
        ),
    ) -> DownloadedTwilioMedia:

        return self._download(
            item=item,
            message_sid=message_sid,
            output_dir=output_dir,
            required_prefix="audio/",
        )

    def download_image(
        self,
        *,
        item: TwilioMediaItem,
        message_sid: str,
        output_dir: str | Path = (
            "tmp/inbound_receipts"
        ),
    ) -> DownloadedTwilioMedia:

        return self._download(
            item=item,
            message_sid=message_sid,
            output_dir=output_dir,
            required_prefix="image/",
        )

    def _download(
        self,
        *,
        item: TwilioMediaItem,
        message_sid: str,
        output_dir: str | Path,
        required_prefix: str,
    ) -> DownloadedTwilioMedia:

        parsed = urlparse(
            item.url
        )

        if parsed.scheme.lower() != "https":
            raise TwilioMediaError(
                "Twilio media URL must use HTTPS."
            )

        output_dir = Path(
            output_dir
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        response = requests.get(
            item.url,
            auth=(
                self.account_sid,
                self.auth_token,
            ),
            stream=True,
            allow_redirects=True,
            timeout=(
                10,
                self.timeout_seconds,
            ),
        )

        if not response.ok:
            raise TwilioMediaError(
                "Failed to download Twilio media: "
                f"{response.status_code} "
                f"{response.text[:300]}"
            )

        response_content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            .split(";", 1)[0]
            .strip()
            .lower()
        )

        content_type = (
            response_content_type
            if response_content_type.startswith(
                required_prefix
            )
            else item.content_type
        )

        if not content_type.startswith(
            required_prefix
        ):
            raise TwilioMediaError(
                "Downloaded Twilio media has "
                "an unexpected content type."
            )

        content_length = (
            response.headers.get(
                "Content-Length"
            )
        )

        if content_length:
            try:
                if int(content_length) > (
                    self.max_bytes
                ):
                    raise TwilioMediaError(
                        "Media exceeds the "
                        "maximum allowed size."
                    )
            except ValueError:
                pass

        suffix = self._suffix_for(
            content_type
        )

        safe_sid = (
            message_sid
            .strip()
            .replace("/", "_")
            .replace("\\", "_")
        )

        path = (
            output_dir
            / f"{safe_sid}{suffix}"
        )

        total = 0

        try:
            with path.open(
                "wb"
            ) as output_file:

                for chunk in (
                    response.iter_content(
                        chunk_size=64 * 1024
                    )
                ):

                    if not chunk:
                        continue

                    total += len(chunk)

                    if total > self.max_bytes:
                        raise TwilioMediaError(
                            "Media exceeds the "
                            "maximum allowed size."
                        )

                    output_file.write(
                        chunk
                    )

        except Exception:
            path.unlink(
                missing_ok=True
            )
            raise

        if total == 0:
            path.unlink(
                missing_ok=True
            )

            raise TwilioMediaError(
                "Downloaded Twilio media "
                "was empty."
            )

        return DownloadedTwilioMedia(
            path=path,
            content_type=content_type,
        )

    @staticmethod
    def _suffix_for(
        content_type: str,
    ) -> str:

        mapping = {
            "audio/ogg": ".ogg",
            "audio/opus": ".opus",
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/mp4": ".m4a",
            "audio/x-m4a": ".m4a",
            "audio/webm": ".webm",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/amr": ".amr",
            "audio/amr-wb": ".amr",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
        }

        return mapping.get(
            content_type,
            ".media",
        )
