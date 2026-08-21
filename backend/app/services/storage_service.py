"""
Object Storage Service — S3-compatible (MinIO / AWS S3).

Handles upload, download, and presigned URL generation for:
  • audio/   — raw and normalized audio files
  • docs/    — supporting documents and attachments
"""
from __future__ import annotations

import logging
import uuid
import os
from io import BytesIO
from typing import Optional

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectionError

from app.config import settings

logger = logging.getLogger(__name__)

# Fallback directory if MinIO isn't running
LOCAL_STORAGE_DIR = "/tmp/grievance_storage_fallback"
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)


class StorageService:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.STORAGE_ENDPOINT_URL if not settings.STORAGE_USE_SSL else None,
            aws_access_key_id=settings.STORAGE_ACCESS_KEY,
            aws_secret_access_key=settings.STORAGE_SECRET_KEY,
            config=Config(signature_version="s3v4", connect_timeout=1, read_timeout=1, retries={'max_attempts': 0}),
            region_name="ap-south-1",
        )
        self._audio_bucket = settings.STORAGE_BUCKET_AUDIO
        self._docs_bucket = settings.STORAGE_BUCKET_DOCS
        
        self.use_mock = False
        try:
            self._client.list_buckets() # Test connection quickly
        except Exception:
            logger.warning("MinIO is unreachable. Falling back to local disk storage.")
            self.use_mock = True

    def ensure_buckets(self) -> None:
        """Create buckets if they don't exist (called on startup)."""
        if self.use_mock:
            return
            
        for bucket in (self._audio_bucket, self._docs_bucket):
            try:
                self._client.head_bucket(Bucket=bucket)
            except ClientError as exc:
                code = exc.response["Error"]["Code"]
                if code in ("404", "NoSuchBucket"):
                    self._client.create_bucket(Bucket=bucket)
                    logger.info("Created storage bucket: %s", bucket)
                else:
                    raise

    def upload_audio(self, audio_bytes: bytes, extension: str = "wav") -> str:
        """Upload audio bytes to object storage or local fallback."""
        key = f"audio_{uuid.uuid4().hex}.{extension}"
        
        if self.use_mock:
            path = os.path.join(LOCAL_STORAGE_DIR, key)
            with open(path, "wb") as f:
                f.write(audio_bytes)
            return key

        self._client.put_object(
            Bucket=self._audio_bucket,
            Key=key,
            Body=BytesIO(audio_bytes),
            ContentType=f"audio/{extension}",
        )
        return key

    def download_audio(self, key: str) -> bytes:
        """Download audio bytes by storage key."""
        if self.use_mock:
            path = os.path.join(LOCAL_STORAGE_DIR, key)
            with open(path, "rb") as f:
                return f.read()
                
        response = self._client.get_object(Bucket=self._audio_bucket, Key=key)
        return response["Body"].read()

    def presigned_audio_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a time-limited presigned URL for audio playback."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._audio_bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def upload_document(self, doc_bytes: bytes, filename: str, content_type: str) -> str:
        """Upload a document attachment. Returns storage key."""
        key = f"docs/{uuid.uuid4().hex}/{filename}"
        self._client.put_object(
            Bucket=self._docs_bucket,
            Key=key,
            Body=BytesIO(doc_bytes),
            ContentType=content_type,
        )
        return key

    def delete_object(self, bucket: str, key: str) -> None:
        try:
            self._client.delete_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            logger.warning("Failed to delete %s/%s: %s", bucket, key, exc)


storage_service = StorageService()
