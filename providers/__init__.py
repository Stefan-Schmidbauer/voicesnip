"""
Provider registry for Speech-to-Text providers.

To add a new provider:
1. Create a new file in this directory (e.g., openai.py)
2. Implement STTProvider abstract base class
3. Add a registry entry to PROVIDER_REGISTRY below
4. Add the feature to installation_profiles.ini
"""

from typing import List, Dict, Any, Optional
from .base import STTProvider
from .deepgram import DeepgramProvider
from .whisper import WhisperProvider
from .stt_server_dynamic import SttServerDynamicProvider
from .stt_server_fixed import SttServerFixedProvider
from .whisper_rocm import WhisperROCmProvider


# Self-describing provider registry
PROVIDER_REGISTRY: List[Dict[str, Any]] = [
    {
        'key': 'whisper-local-cpu',
        'class': WhisperProvider,
        'display_name': 'Whisper Local CPU (Free)',
        'config_key': 'whisper',
        'features': ['whisper'],
    },
    {
        'key': 'whisper-local-gpu',
        'class': WhisperProvider,
        'display_name': 'Whisper Local GPU (Free, CUDA)',
        'config_key': 'whisper',
        'features': ['whisper', 'cuda'],
    },
    {
        'key': 'whisper-local-rocm',
        'class': WhisperROCmProvider,
        'display_name': 'Whisper Local GPU (Free, ROCm)',
        'config_key': 'whisper',
        'features': ['whisper', 'rocm'],
    },
    {
        'key': 'stt-server-fixed',
        'class': SttServerFixedProvider,
        'display_name': 'STT Server (Fixed Model)',
        'config_key': 'stt-fixed',
        'features': ['stt-fixed'],
    },
    {
        'key': 'stt-server-dynamic',
        'class': SttServerDynamicProvider,
        'display_name': 'STT Server (Model Selection)',
        'config_key': 'stt-dynamic',
        'features': ['stt-dynamic'],
    },
    {
        'key': 'deepgram-cloud',
        'class': DeepgramProvider,
        'display_name': 'Deepgram Cloud (API Key required)',
        'config_key': 'deepgram',
        'features': ['deepgram'],
    },
]


def get_providers_for_features(features: List[str]) -> List[Dict[str, Any]]:
    """Return registry entries whose required features are all present in the given feature list.

    Args:
        features: List of enabled feature strings (e.g. ['whisper', 'deepgram', 'cuda'])

    Returns:
        List of matching registry entry dicts
    """
    result = []
    for entry in PROVIDER_REGISTRY:
        if all(f in features for f in entry['features']):
            result.append(entry)
    return result


def get_registry_entry(key: str) -> Optional[Dict[str, Any]]:
    """Return the registry entry for the given provider key.

    Args:
        key: Provider key (e.g. 'whisper-local-cpu', 'stt-server-dynamic')

    Returns:
        Registry entry dict or None if not found
    """
    for entry in PROVIDER_REGISTRY:
        if entry['key'] == key:
            return entry
    return None


def create_provider(name: str, **config) -> STTProvider:
    """
    Factory method to create provider instance.

    Args:
        name: Provider key (e.g. 'whisper-local-cpu', 'stt-server-dynamic', 'stt-server-fixed')
        **config: Provider-specific configuration

    Returns:
        Initialized provider instance

    Raises:
        ValueError: If provider name is unknown
    """
    entry = get_registry_entry(name.lower())
    if entry is None:
        available = ', '.join(e['key'] for e in PROVIDER_REGISTRY)
        raise ValueError(f"Unknown provider '{name}'. Available: {available}")

    # Extract device info from provider name for Whisper
    if name.lower().startswith('whisper-local-'):
        device = 'cuda' if 'gpu' in name.lower() else 'cpu'
        config['device'] = device

    return entry['class'](**config)


# Export public API
__all__ = [
    'STTProvider',
    'DeepgramProvider',
    'WhisperProvider',
    'SttServerDynamicProvider',
    'SttServerFixedProvider',
    'WhisperROCmProvider',
    'PROVIDER_REGISTRY',
    'get_providers_for_features',
    'get_registry_entry',
    'create_provider',
]
