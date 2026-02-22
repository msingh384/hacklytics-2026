from __future__ import annotations

import logging
from io import BytesIO
from typing import TYPE_CHECKING

from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger(__name__)


class ElevenLabsClient:
    """Thin wrapper around the ElevenLabs Python SDK for text-to-speech."""

    def __init__(self, settings: Settings):
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.model_id = settings.elevenlabs_model_id
        self._client: ElevenLabs | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @property
    def client(self) -> ElevenLabs:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("ELEVENLABS_API_KEY is not configured")
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    def generate_speech(self, text: str, *, voice_id: str | None = None) -> bytes:
        """Convert *text* to an MP3 audio buffer using ElevenLabs streaming TTS.

        Returns raw MP3 bytes that can be sent directly as an HTTP response.
        """
        response = self.client.text_to_speech.convert(
            voice_id=voice_id or self.voice_id,
            output_format="mp3_44100_128",
            text=text,
            model_id=self.model_id,
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True,
            ),
        )

        buf = BytesIO()
        for chunk in response:
            if chunk:
                buf.write(chunk)
        buf.seek(0)
        logger.info("ElevenLabs TTS generated %d bytes for %d chars of text", buf.getbuffer().nbytes, len(text))
        return buf.read()
