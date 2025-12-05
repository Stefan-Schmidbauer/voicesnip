"""
Base provider interface for Speech-to-Text providers.

This module defines the abstract base class that all STT providers must implement.
"""

from abc import ABC, abstractmethod
from typing import Optional, List


class STTProvider(ABC):
    """Abstract base class for Speech-to-Text providers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name"""
        pass

    @abstractmethod
    def validate_config(self) -> None:
        """
        Validate provider configuration.

        Raises:
            ValueError: If configuration is invalid or incomplete
        """
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """
        Return list of available models for this provider.

        Returns:
            List of model identifiers
        """
        pass

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio to text.

        Args:
            audio_bytes: WAV format audio data
            language: ISO language code (e.g., 'en', 'de') or None for auto-detect

        Returns:
            Transcribed text or None on error
        """
        pass

    def unload_model(self) -> None:
        """
        Unload model from memory/VRAM (optional, for providers that load models).
        Default implementation does nothing - override in subclasses that need cleanup.
        """
        pass

    def is_model_downloaded(self) -> bool:
        """
        Check if the model is already downloaded and cached locally.

        Returns:
            True if model is downloaded, False if it needs to be downloaded.
            Default implementation returns True (for cloud providers).
        """
        return True
