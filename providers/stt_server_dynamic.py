"""
STT Server (Model Selection) Provider

Provides speech-to-text using any OpenAI-compatible STT server API.
The client selects the model — the server provides a list of available models.
Works with Speaches, whisper-asr-webservice, or any server exposing /v1/audio/transcriptions.
"""

import os
import requests
from typing import Optional, List
from .base import STTProvider

# Well-known faster-whisper models (always shown, even if server is unreachable)
KNOWN_MODELS = [
    "Systran/faster-whisper-large-v3",
    "Systran/faster-whisper-medium",
    "Systran/faster-whisper-small",
    "Systran/faster-whisper-base",
    "Systran/faster-whisper-tiny",
    "Systran/faster-distil-whisper-large-v3",
]


class SttServerDynamicProvider(STTProvider):
    """STT Server (Model Selection) provider — client selects the model"""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None,
                 verify_ssl: Optional[bool] = None, model: Optional[str] = None,
                 allowed_models: Optional[str] = None, **kwargs):
        """
        Initialize STT Server Dynamic provider.

        Args:
            endpoint: API endpoint URL (defaults to STT_DYNAMIC_ENDPOINT env var)
            api_key: Optional API key for authentication (defaults to STT_DYNAMIC_API_KEY env var)
            verify_ssl: Whether to verify SSL certificates (defaults to STT_DYNAMIC_VERIFY_SSL env var, True if not set)
            model: Hugging Face model identifier (defaults to STT_DYNAMIC_MODEL env var)
            allowed_models: Comma-separated list of allowed model IDs to filter the model list
                           (defaults to STT_DYNAMIC_ALLOWED_MODELS env var)
            **kwargs: Ignored (allows generic config forwarding)
        """
        self.endpoint = endpoint or os.getenv("STT_DYNAMIC_ENDPOINT",
                                              "http://localhost:8000/v1/audio/transcriptions")
        self.api_key = api_key or os.getenv("STT_DYNAMIC_API_KEY")
        self.model = model or os.getenv("STT_DYNAMIC_MODEL", "Systran/faster-whisper-large-v3")

        # Allowed models filter (from INI config or env var)
        allowed = allowed_models or os.getenv("STT_DYNAMIC_ALLOWED_MODELS")
        if allowed:
            self.allowed_models = [m.strip() for m in allowed.split(',') if m.strip()]
        else:
            self.allowed_models = None

        # SSL verification - defaults to True unless explicitly disabled
        if verify_ssl is not None:
            self.verify_ssl = verify_ssl
        else:
            env_verify = os.getenv("STT_DYNAMIC_VERIFY_SSL", "true").lower()
            self.verify_ssl = env_verify not in ("false", "0", "no")

    @property
    def name(self) -> str:
        return "STT Server (Model Selection)"

    def _get_base_url(self) -> str:
        """Get base URL from endpoint (strip /v1/audio/transcriptions)"""
        return self.endpoint.replace("/v1/audio/transcriptions", "")

    def validate_config(self) -> None:
        """Validate STT Server Dynamic configuration"""
        if not self.endpoint:
            raise ValueError("STT_DYNAMIC_ENDPOINT not set")
        if not self.model:
            raise ValueError("STT_DYNAMIC_MODEL not set")

        # Test connection to server
        try:
            health_url = self._get_base_url() + "/health"
            response = requests.get(health_url, timeout=5, verify=self.verify_ssl)
            if response.status_code != 200:
                raise ValueError(f"STT server health check failed: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise ValueError(f"Cannot connect to STT server at {self.endpoint}")
        except requests.exceptions.Timeout:
            raise ValueError(f"STT server timeout at {self.endpoint}")

    def get_available_models(self) -> List[str]:
        """
        Return available models from the STT server.

        1. Start with KNOWN_MODELS (hardcoded)
        2. Try to query /v1/models from server — merge any new models
        3. If allowed_models is set, filter to only those
        """
        models = list(KNOWN_MODELS)

        # Try to merge models from server
        try:
            models_url = self._get_base_url() + "/v1/models"
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            response = requests.get(models_url, timeout=5, verify=self.verify_ssl, headers=headers)
            if response.status_code == 200:
                result = response.json()
                server_models = [m['id'] for m in result.get('data', []) if 'id' in m]
                for m in server_models:
                    if m not in models:
                        models.append(m)
        except (requests.exceptions.RequestException, ValueError, KeyError):
            pass

        # Filter by allowed_models if set
        if self.allowed_models:
            models = [m for m in models if m in self.allowed_models]

        return models

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
            data = {
                'model': self.model,
            }
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
