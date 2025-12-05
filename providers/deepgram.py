"""
Deepgram Cloud STT Provider

Provides speech-to-text using Deepgram's cloud API.
Requires API key and internet connection.
"""

import os
import requests
from typing import Optional, List
from .base import STTProvider


class DeepgramProvider(STTProvider):
    """Deepgram Cloud STT provider"""

    def __init__(self, api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 endpoint: Optional[str] = None):
        """
        Initialize Deepgram provider.

        Args:
            api_key: Deepgram API key (defaults to DEEPGRAM_API_KEY env var)
            model: Model identifier (defaults to DEEPGRAM_MODEL env var)
            endpoint: API endpoint URL (defaults to DEEPGRAM_ENDPOINT env var)
        """
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.model = model or os.getenv("DEEPGRAM_MODEL", "nova-2-general")
        self.endpoint = endpoint or os.getenv("DEEPGRAM_ENDPOINT",
                                              "https://api.eu.deepgram.com/v1/listen")

    @property
    def name(self) -> str:
        return "Deepgram"

    def validate_config(self) -> None:
        """Validate Deepgram configuration"""
        if not self.api_key or self.api_key == "your_api_key_here":
            raise ValueError("DEEPGRAM_API_KEY not set in .env file")
        if not self.model:
            raise ValueError("DEEPGRAM_MODEL not set")
        if not self.endpoint:
            raise ValueError("DEEPGRAM_ENDPOINT not set")

    def get_available_models(self) -> List[str]:
        """Return available Deepgram models"""
        return [
            "nova-2-general",
            "nova-2"
        ]

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using Deepgram API.

        Args:
            audio_bytes: WAV format audio data
            language: ISO language code or None for auto-detect

        Returns:
            Transcribed text or None on error
        """
        params = {
            'model': self.model,
            'punctuate': 'true',
            'smart_format': 'true'
        }

        if language:
            params['language'] = language

        headers = {
            'Authorization': f'Token {self.api_key}',
            'Content-Type': 'audio/wav'
        }

        try:
            response = requests.post(
                self.endpoint,
                params=params,
                headers=headers,
                data=audio_bytes,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                transcript = result.get('results', {}).get('channels', [{}])[0]\
                    .get('alternatives', [{}])[0].get('transcript', '')
                return transcript.strip()
            elif response.status_code == 401:
                # Invalid API key
                print(f"Deepgram API Error: {response.status_code} - {response.text}")
                raise ValueError("Invalid Deepgram API key")
            elif response.status_code == 403:
                # Access forbidden
                print(f"Deepgram API Error: {response.status_code} - {response.text}")
                raise ValueError("Deepgram API access forbidden (check API key permissions)")
            else:
                # Other API errors
                print(f"Deepgram API Error: {response.status_code} - {response.text}")
                raise RuntimeError(f"Deepgram API returned status code {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"Deepgram network error: {e}")
            raise RuntimeError(f"Network error: {str(e)}")
