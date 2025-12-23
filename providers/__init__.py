"""
Provider registry for Speech-to-Text providers.

To add a new provider:
1. Create a new file in this directory (e.g., openai.py)
2. Implement STTProvider abstract base class
3. Add import and registration below
4. Update .env.example with configuration template
"""

from typing import Dict, Type
from .base import STTProvider
from .deepgram import DeepgramProvider
from .whisper import WhisperProvider
from .faster_whisper_server import FasterWhisperServerProvider


# Provider Registry
PROVIDERS: Dict[str, Type[STTProvider]] = {
    'deepgram-cloud': DeepgramProvider,
    'whisper-local-cpu': WhisperProvider,
    'whisper-local-gpu': WhisperProvider,
    'faster-whisper-server': FasterWhisperServerProvider,
}


def create_provider(name: str, **config) -> STTProvider:
    """
    Factory method to create provider instance.

    Args:
        name: Provider name ('whisper-local-cpu', 'whisper-local-gpu', 'deepgram-cloud', 'faster-whisper-server')
        **config: Provider-specific configuration

    Returns:
        Initialized provider instance

    Raises:
        ValueError: If provider name is unknown
    """
    name_lower = name.lower()
    if name_lower not in PROVIDERS:
        available = ', '.join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    # Extract device info from provider name for Whisper
    if name_lower.startswith('whisper-local-'):
        device = 'cuda' if 'gpu' in name_lower else 'cpu'
        config['device'] = device

    return PROVIDERS[name_lower](**config)


# Export public API
__all__ = [
    'STTProvider',
    'DeepgramProvider',
    'WhisperProvider',
    'FasterWhisperServerProvider',
    'create_provider',
    'PROVIDERS',
]
