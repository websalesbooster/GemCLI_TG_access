"""Transcription service using faster-whisper for voice note processing."""

import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import ContextManager
from contextlib import contextmanager

from faster_whisper import WhisperModel


class TranscriptionService:
    """Transcribes voice notes to text using faster-whisper."""

    def __init__(self, model: str = "small", compute_type: str = "int8", timeout: int = 30):
        """Initialize the transcription service.

        Args:
            model: The faster-whisper model to use (default: "small")
            compute_type: Compute type for inference (default: "int8")
            timeout: Maximum seconds for transcription (default: 30)
        """
        self._model = WhisperModel(model, compute_type=compute_type)
        self._timeout = timeout

    @contextmanager
    def _temp_directory(self) -> ContextManager[Path]:
        """Create and manage a unique temporary directory.

        Yields:
            Path to the temporary directory.

        Always cleans up the directory after the context exits.
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="telegram_codex_"))
        try:
            yield temp_dir
        finally:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def transcribe(self, audio_path: Path) -> str:
        """Synchronously transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file to transcribe.

        Returns:
            Transcribed text.

        Raises:
            ValueError: If audio duration exceeds 180 seconds.
        """
        segments, info = self._model.transcribe(
            str(audio_path),
            word_timestamps=False,
            vad_filter=True
        )

        # Validate duration after getting info
        if info.duration and info.duration > 180:
            raise ValueError(f"Voice note too long: {info.duration:.1f}s (max: 180s)")

        # Collect all transcribed text
        text_parts = []
        for segment in segments:
            if segment.text:
                text_parts.append(segment.text.strip())

        return " ".join(text_parts)

    async def transcribe_async(self, audio_path: Path) -> str:
        """Asynchronously transcribe an audio file to text.

        This method:
        - Creates a unique temporary directory
        - Runs transcription in a worker thread
        - Enforces 30-second timeout
        - Always cleans up the temporary directory

        Args:
            audio_path: Path to the audio file to transcribe.

        Returns:
            Transcribed text.

        Raises:
            ValueError: If audio duration exceeds 180 seconds.
            asyncio.TimeoutError: If transcription exceeds timeout.
        """
        with self._temp_directory():
            return await asyncio.wait_for(
                asyncio.to_thread(self.transcribe, audio_path),
                timeout=self._timeout
            )