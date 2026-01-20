"""
Faster Whisper Server STT Provider

Provides speech-to-text using Faster Whisper Server API (Docker container).
Compatible with OpenAI Whisper API format.
No API key required, works over local network.
"""

import os
import requests
from typing import Optional, List
from .base import STTProvider


class FasterWhisperServerProvider(STTProvider):
    """Faster Whisper Server STT provider (network/remote server)"""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None,
                 verify_ssl: Optional[bool] = None):
        """
        Initialize Faster Whisper Server provider.

        Args:
            endpoint: API endpoint URL (defaults to FASTER_WHISPER_ENDPOINT env var)
            api_key: Optional API key for authentication (defaults to FASTER_WHISPER_API_KEY env var)
            verify_ssl: Whether to verify SSL certificates (defaults to FASTER_WHISPER_VERIFY_SSL env var, True if not set)

        Note:
            The model is configured on the Faster Whisper Server itself.
            The server will use whatever model it was configured with.
        """
        self.endpoint = endpoint or os.getenv("FASTER_WHISPER_ENDPOINT",
                                              "http://localhost:8000/v1/audio/transcriptions")
        self.api_key = api_key or os.getenv("FASTER_WHISPER_API_KEY")

        # SSL verification - defaults to True unless explicitly disabled
        if verify_ssl is not None:
            self.verify_ssl = verify_ssl
        else:
            env_verify = os.getenv("FASTER_WHISPER_VERIFY_SSL", "true").lower()
            self.verify_ssl = env_verify not in ("false", "0", "no")

    @property
    def name(self) -> str:
        return "Faster Whisper Server"

    def validate_config(self) -> None:
        """Validate Faster Whisper Server configuration"""
        if not self.endpoint:
            raise ValueError("FASTER_WHISPER_ENDPOINT not set")

        # Test connection to server
        try:
            health_url = self.endpoint.replace("/v1/audio/transcriptions", "/health")
            response = requests.get(health_url, timeout=5, verify=self.verify_ssl)
            if response.status_code != 200:
                raise ValueError(f"Faster Whisper Server health check failed: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise ValueError(f"Cannot connect to Faster Whisper Server at {self.endpoint}")
        except requests.exceptions.Timeout:
            raise ValueError(f"Faster Whisper Server timeout at {self.endpoint}")

    def get_available_models(self) -> List[str]:
        """
        Return available Faster Whisper models.

        Note: The actual model used is determined by the server configuration.
        Returns empty list because model selection is not applicable for this provider.
        """
        return []

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using Faster Whisper Server API.

        Args:
            audio_bytes: WAV format audio data
            language: ISO language code ('de', 'en') or None for auto-detect

        Returns:
            Transcribed text or None on error
        """
        try:
            # Prepare multipart form data (OpenAI-compatible format)
            files = {
                'file': ('audio.wav', audio_bytes, 'audio/wav')
            }
            data = {}
            if language:
                data['language'] = language

            # Prepare headers with optional API key
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            response = requests.post(
                self.endpoint,
                files=files,
                data=data,
                headers=headers,
                timeout=300,  # Long timeout for first-time model download (5 minutes)
                verify=self.verify_ssl
            )

            if response.status_code == 200:
                result = response.json()
                transcript = result.get('text', '').strip()
                return transcript if transcript else None
            else:
                print(f"Faster Whisper Server Error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Faster Whisper Server network error: {e}")
            return None
