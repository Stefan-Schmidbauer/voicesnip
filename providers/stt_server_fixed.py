"""
STT Server (Fixed Model) Provider

Provides speech-to-text using any OpenAI-compatible STT server API.
The model is configured on the server itself — the client sends audio without model selection.
Works with faster-whisper-server, insanely-fast-whisper-rocm, or any server exposing /v1/audio/transcriptions.
"""

import os
import requests
from typing import Optional, List
from .base import STTProvider


class SttServerFixedProvider(STTProvider):
    """STT Server (Fixed Model) provider — model configured on server"""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None,
                 verify_ssl: Optional[bool] = None, **kwargs):
        """
        Initialize STT Server Fixed provider.

        Args:
            endpoint: API endpoint URL (defaults to STT_FIXED_ENDPOINT env var)
            api_key: Optional API key for authentication (defaults to STT_FIXED_API_KEY env var)
            verify_ssl: Whether to verify SSL certificates (defaults to STT_FIXED_VERIFY_SSL env var, True if not set)
            **kwargs: Ignored (allows generic config forwarding)

        Note:
            The model is configured on the server itself.
            The server will use whatever model it was configured with.
        """
        self.endpoint = endpoint or os.getenv("STT_FIXED_ENDPOINT",
                                              "http://localhost:8000/v1/audio/transcriptions")
        self.api_key = api_key or os.getenv("STT_FIXED_API_KEY")

        # SSL verification - defaults to True unless explicitly disabled
        if verify_ssl is not None:
            self.verify_ssl = verify_ssl
        else:
            env_verify = os.getenv("STT_FIXED_VERIFY_SSL", "true").lower()
            self.verify_ssl = env_verify not in ("false", "0", "no")

    @property
    def name(self) -> str:
        return "STT Server (Fixed Model)"

    def validate_config(self) -> None:
        """Validate STT Server Fixed configuration"""
        if not self.endpoint:
            raise ValueError("STT_FIXED_ENDPOINT not set")

        # Test connection to server
        try:
            health_url = self.endpoint.replace("/v1/audio/transcriptions", "/health")
            response = requests.get(health_url, timeout=5, verify=self.verify_ssl)
            if response.status_code != 200:
                raise ValueError(f"STT server health check failed: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise ValueError(f"Cannot connect to STT server at {self.endpoint}")
        except requests.exceptions.Timeout:
            raise ValueError(f"STT server timeout at {self.endpoint}")

    def get_available_models(self) -> List[str]:
        """
        Return available models.

        Returns empty list because model selection is not applicable for this provider.
        The model is configured on the server itself.
        """
        return []

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using the STT server API.

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
            elif response.status_code in (401, 403):
                raise ValueError(f"Authentication failed ({response.status_code})")
            else:
                raise RuntimeError(f"Server error ({response.status_code})")

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error: {e}")
