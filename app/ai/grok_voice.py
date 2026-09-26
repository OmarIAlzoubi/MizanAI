from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


XAI_BASE_URL = "https://api.x.ai/v1"


class GrokVoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str | None
    duration: float | None


class GrokVoice:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        voice_id: str = "ara",
        tts_language: str = "ar-SA",
        stt_model: str = "grok-voice-transcribe-2.0",
        timeout_seconds: int = 120,
    ):
        self.api_key = (
            api_key
            or os.getenv("XAI_API_KEY")
        )

        if not self.api_key:
            raise GrokVoiceError(
                "XAI_API_KEY was not found."
            )

        self.voice_id = voice_id
        self.tts_language = tts_language
        self.stt_model = stt_model
        self.timeout_seconds = timeout_seconds

        self.headers = {
            "Authorization":
                f"Bearer {self.api_key}"
        }

    # =========================================================
    # TEXT TO SPEECH
    # =========================================================

    def synthesize(
        self,
        *,
        text: str,
        output_path: str | Path,
        language: str | None = None,
    ) -> Path:

        text = text.strip()

        if not text:
            raise GrokVoiceError(
                "TTS text cannot be empty."
            )

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        response = requests.post(
            f"{XAI_BASE_URL}/tts",
            headers={
                **self.headers,
                "Content-Type":
                    "application/json",
            },
            json={
                "text":
                    text,

                "voice_id":
                    self.voice_id,

                "language":
                    (
                        language
                        or self.tts_language
                    ),

                "text_normalization":
                    True,

                "output_format": {
                    "codec":
                        "mp3",

                    "sample_rate":
                        24000,

                    "bit_rate":
                        128000,
                },
            },
            timeout=self.timeout_seconds,
        )

        if not response.ok:
            raise GrokVoiceError(
                "Grok TTS failed: "
                f"{response.status_code} "
                f"{response.text[:500]}"
            )

        if not response.content:
            raise GrokVoiceError(
                "Grok TTS returned empty audio."
            )

        output_path.write_bytes(
            response.content
        )

        return output_path

    # =========================================================
    # SPEECH TO TEXT
    # =========================================================

    def transcribe(
        self,
        *,
        audio_path: str | Path,
        language: str | None = None,
    ) -> TranscriptionResult:

        audio_path = Path(
            audio_path
        )

        if not audio_path.exists():
            raise GrokVoiceError(
                f"Audio file does not exist: "
                f"{audio_path}"
            )

        content_type = (
            self._content_type(
                audio_path
            )
        )

        with audio_path.open(
            "rb"
        ) as audio_file:

            data = {
                "model": self.stt_model,
                "format": "false",
            }

            response = requests.post(
                f"{XAI_BASE_URL}/stt",
                headers=self.headers,
                data=data,
                files={
                    "file": (
                        audio_path.name,
                        audio_file,
                        content_type,
                    )
                },
                timeout=self.timeout_seconds,
            )

        if not response.ok:
            raise GrokVoiceError(
                "Grok STT failed: "
                f"{response.status_code} "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise GrokVoiceError(
                "Grok STT returned invalid JSON."
            ) from exc

        text = str(
            payload.get("text")
            or ""
        ).strip()

        if not text:
            raise GrokVoiceError(
                "Grok STT returned empty text."
            )

        return TranscriptionResult(
            text=text,

            language=(
                payload.get("language")
            ),

            duration=(
                payload.get("duration")
            ),
        )

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _content_type(
        path: Path,
    ) -> str:

        suffix = (
            path.suffix
            .lower()
        )

        mapping = {
            ".mp3":
                "audio/mpeg",

            ".wav":
                "audio/wav",

            ".ogg":
                "audio/ogg",

            ".opus":
                "audio/ogg",

            ".m4a":
                "audio/mp4",

            ".webm":
                "audio/webm",
        }

        return mapping.get(
            suffix,
            "application/octet-stream",
        )