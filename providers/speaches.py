"""
Speaches STT Provider

Provides speech-to-text using Speaches server API (Docker container).
Compatible with OpenAI Whisper API format.
No API key required, works over local network.
"""

import os
import requests
from typing import Optional, List
from .base import STTProvider

# Well-known faster-whisper models as fallback when server is unreachable
FALLBACK_MODELS = [
    "Systran/faster-whisper-large-v3",
    "Systran/faster-whisper-medium",
    "Systran/faster-whisper-small",
    "Systran/faster-whisper-base",
    "Systran/faster-whisper-tiny",
    "Systran/faster-distil-whisper-large-v3",
]


class SpeachesProvider(STTProvider):
    """Speaches STT provider (network/remote server)"""

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None,
                 verify_ssl: Optional[bool] = None, model: Optional[str] = None):
        """
        Initialize Speaches provider.

        Args:
            endpoint: API endpoint URL (defaults to SPEACHES_ENDPOINT env var)
            api_key: Optional API key for authentication (defaults to SPEACHES_API_KEY env var)
            verify_ssl: Whether to verify SSL certificates (defaults to SPEACHES_VERIFY_SSL env var, True if not set)
            model: Hugging Face model identifier (defaults to SPEACHES_MODEL env var)
        """
        self.endpoint = endpoint or os.getenv("SPEACHES_ENDPOINT",
                                              "http://localhost:8000/v1/audio/transcriptions")
        self.api_key = api_key or os.getenv("SPEACHES_API_KEY")
        self.model = model or os.getenv("SPEACHES_MODEL", "Systran/faster-whisper-large-v3")

        # SSL verification - defaults to True unless explicitly disabled
        if verify_ssl is not None:
            self.verify_ssl = verify_ssl
        else:
            env_verify = os.getenv("SPEACHES_VERIFY_SSL", "true").lower()
            self.verify_ssl = env_verify not in ("false", "0", "no")

    @property
    def name(self) -> str:
        return "Speaches"

    def _get_base_url(self) -> str:
        """Get base URL from endpoint (strip /v1/audio/transcriptions)"""
        return self.endpoint.replace("/v1/audio/transcriptions", "")

    def validate_config(self) -> None:
        """Validate Speaches configuration"""
        if not self.endpoint:
            raise ValueError("SPEACHES_ENDPOINT not set")
        if not self.model:
            raise ValueError("SPEACHES_MODEL not set")

        # Test connection to server
        try:
            health_url = self._get_base_url() + "/health"
            response = requests.get(health_url, timeout=5, verify=self.verify_ssl)
            if response.status_code != 200:
                raise ValueError(f"Speaches server health check failed: {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise ValueError(f"Cannot connect to Speaches server at {self.endpoint}")
        except requests.exceptions.Timeout:
            raise ValueError(f"Speaches server timeout at {self.endpoint}")

    def get_available_models(self) -> List[str]:
        """
        Query available models from the Speaches server.

        Falls back to a list of well-known faster-whisper models if the server
        is unreachable.
        """
        try:
            models_url = self._get_base_url() + "/v1/models"
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'

            response = requests.get(models_url, timeout=5, verify=self.verify_ssl, headers=headers)
            if response.status_code == 200:
                result = response.json()
                model_ids = [m['id'] for m in result.get('data', []) if 'id' in m]
                if model_ids:
                    return model_ids
        except (requests.exceptions.RequestException, ValueError, KeyError):
            pass

        # Fallback: return well-known models
        return FALLBACK_MODELS

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using Speaches server API.

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
