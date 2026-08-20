"""
Audio Service — FFmpeg-based normalization pipeline.

Normalizes uploaded audio to the format required by IndicASR:
  • Mono channel
  • 16 kHz sample rate
  • -23 LUFS loudness normalization (EBU R128)
  • 16-bit PCM WAV output
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Supported input MIME types / extensions
SUPPORTED_FORMATS = {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".webm", ".aac", ".opus"}


class AudioProcessingError(RuntimeError):
    pass


class AudioService:
    def __init__(self) -> None:
        self.tmp_dir = Path(settings.AUDIO_TMP_DIR)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = settings.FFMPEG_PATH

    async def normalize(self, input_bytes: bytes, original_filename: str) -> tuple[bytes, int]:
        """
        Normalize raw audio bytes using FFmpeg.

        Args:
            input_bytes:       Raw bytes of the uploaded audio file.
            original_filename: Original filename (used for format detection).

        Returns:
            Tuple of (normalized WAV bytes, duration_seconds).

        Raises:
            AudioProcessingError: If FFmpeg fails or format is unsupported.
        """
        suffix = Path(original_filename).suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise AudioProcessingError(
                f"Unsupported audio format '{suffix}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        run_id = uuid.uuid4().hex
        input_path = self.tmp_dir / f"{run_id}_input{suffix}"
        output_path = self.tmp_dir / f"{run_id}_normalized.wav"

        try:
            # Write upload to temp file
            input_path.write_bytes(input_bytes)

            # FFmpeg command:
            # -af loudnorm: EBU R128 loudness normalization
            # -ar 16000:   resample to 16 kHz
            # -ac 1:       mix down to mono
            # -acodec pcm_s16le: 16-bit PCM
            cmd = [
                self.ffmpeg,
                "-y",                          # overwrite output
                "-i", str(input_path),
                "-af", "loudnorm=I=-23:TP=-2:LRA=11",
                "-ar", "16000",
                "-ac", "1",
                "-acodec", "pcm_s16le",
                str(output_path),
            ]

            logger.debug("Running FFmpeg: %s", " ".join(cmd))
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise AudioProcessingError(
                    f"FFmpeg failed (exit {proc.returncode}): {stderr.decode()}"
                )

            normalized_bytes = output_path.read_bytes()
            duration = await self._get_duration(output_path)
            logger.info("Audio normalized: %d bytes, %ds", len(normalized_bytes), duration)
            return normalized_bytes, duration

        finally:
            # Clean up temp files
            for p in (input_path, output_path):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass

    async def _get_duration(self, wav_path: Path) -> int:
        """Use ffprobe to get duration in seconds."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(wav_path),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return int(float(stdout.decode().strip()))
        except Exception:
            return 0


audio_service = AudioService()
