from __future__ import annotations

import os
import uuid
from pathlib import Path

from botocore.config import Config

import boto3
from dotenv import load_dotenv


load_dotenv()


class VoiceMediaStoreError(RuntimeError):
    pass


class VoiceMediaStore:
    def __init__(
        self,
        *,
        bucket_name: str | None = None,
        region: str | None = None,
        aws_profile: str | None = None,
    ):
        self.bucket_name = (
            bucket_name
            or os.getenv("MIZAN_VOICE_BUCKET")
        )

        self.region = (
            region
            or os.getenv("AWS_REGION")
            or "eu-central-1"
        )

        self.aws_profile = (
            aws_profile
            or os.getenv("AWS_PROFILE")
        )

        if not self.bucket_name:
            raise VoiceMediaStoreError(
                "MIZAN_VOICE_BUCKET was not found."
            )

        if self.aws_profile:
            session = boto3.Session(
                profile_name=self.aws_profile,
                region_name=self.region,
            )
        else:
            session = boto3.Session(
                region_name=self.region,
            )

        self.s3 = session.client(
            "s3",
            region_name=self.region,
            endpoint_url=(
                f"https://s3.{self.region}.amazonaws.com"
            ),
            config=Config(
                signature_version="s3v4",
                s3={
                    "addressing_style": "virtual",
                },
            ),
        )

    def upload_audio(
        self,
        *,
        file_path: str | Path,
        content_type: str = "audio/mpeg",
    ) -> str:
        file_path = Path(file_path)

        if not file_path.exists():
            raise VoiceMediaStoreError(
                f"Audio file not found: {file_path}"
            )

        suffix = (
            file_path.suffix.lower()
            or ".mp3"
        )

        key = (
            f"voice/"
            f"{uuid.uuid4().hex}"
            f"{suffix}"
        )

        try:
            self.s3.upload_file(
                str(file_path),
                self.bucket_name,
                key,
                ExtraArgs={
                    "ContentType": content_type,
                },
            )

        except Exception as exc:
            raise VoiceMediaStoreError(
                f"Failed to upload voice media: {exc}"
            ) from exc

        return key

    def create_presigned_url(
        self,
        *,
        key: str,
        expires_in: int = 900,
    ) -> str:
        try:
            return self.s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )

        except Exception as exc:
            raise VoiceMediaStoreError(
                f"Failed to create presigned URL: {exc}"
            ) from exc

    def delete(
        self,
        *,
        key: str,
    ) -> None:
        try:
            self.s3.delete_object(
                Bucket=self.bucket_name,
                Key=key,
            )

        except Exception as exc:
            raise VoiceMediaStoreError(
                f"Failed to delete voice media: {exc}"
            ) from exc