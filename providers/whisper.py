"""
Faster Whisper Local STT Provider

Provides speech-to-text using Faster Whisper running locally.
No API key required, works offline, free to use.
"""

import os
import io
from typing import Optional, List
from .base import STTProvider


class WhisperProvider(STTProvider):
    """Faster Whisper local STT provider"""

    def __init__(self, model: Optional[str] = None, device: str = "cpu",
                 compute_type: str = "default"):
        """
        Initialize Faster Whisper provider.

        Args:
            model: Model size (tiny, base, small, medium, large-v2)
            device: Device to use ('cpu' or 'cuda')
            compute_type: Compute type for CTranslate2
        """
        self.model_name = model or os.getenv("WHISPER_MODEL", "small")
        self.device = device
        # Auto-select compute type based on device if not specified
        if compute_type == "default":
            if device == "cuda":
                compute_type = "float16"  # Use float16 on CUDA for better performance
            else:
                compute_type = "int8"  # Use int8 on CPU for better performance
        self.compute_type = compute_type
        self._model = None

    @property
    def name(self) -> str:
        return "Whisper (Local)"

    @property
    def model(self):
        """Lazy load model on first use"""
        if self._model is None:
            from faster_whisper import WhisperModel
            from pathlib import Path

            # Check if model is already downloaded
            cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
            model_cached = False
            if cache_dir.exists():
                # Look for model directory (format: models--Systran--faster-whisper-{model})
                # Special case: turbo is stored as faster-whisper-large-v3-turbo
                search_pattern = "faster-whisper-large-v3-turbo" if self.model_name == "turbo" else f"faster-whisper-{self.model_name}"
                for entry in cache_dir.iterdir():
                    if search_pattern in entry.name:
                        model_cached = True
                        break

            if model_cached:
                print(f"Loading Whisper model '{self.model_name}'...")
            else:
                print(f"Downloading Whisper model '{self.model_name}'...")
                print("(Larger models can take a long time - please be patient)")

            # Try to load with requested device, fallback to CPU on error
            device_to_use = self.device
            compute_type_to_use = self.compute_type

            try:
                self._model = WhisperModel(
                    self.model_name,
                    device=device_to_use,
                    compute_type=compute_type_to_use
                )
                device_info = f"{device_to_use.upper()}"
                if device_to_use == "cuda":
                    device_info += f" (compute_type={compute_type_to_use})"
                print(f"Model '{self.model_name}' ready on {device_info}!")
            except (Exception, SystemError) as e:
                # Catch both Python exceptions and system errors (like cuDNN crashes)
                if device_to_use == "cuda":
                    error_str = str(e).lower()
                    if "cudnn" in error_str or "cuda" in error_str:
                        print(f"Warning: CUDA/cuDNN library error detected")
                        print(f"Details: {e}")
                    else:
                        print(f"Warning: Failed to load model on CUDA: {e}")
                    print("Falling back to CPU mode...")
                    device_to_use = "cpu"
                    compute_type_to_use = "default"
                    try:
                        self._model = WhisperModel(
                            self.model_name,
                            device=device_to_use,
                            compute_type=compute_type_to_use
                        )
                        print(f"Model '{self.model_name}' ready on CPU!")
                        # Update device for future reference
                        self.device = "cpu"
                    except Exception as cpu_error:
                        raise ValueError(f"Failed to load model on both CUDA and CPU: {cpu_error}")
                else:
                    raise ValueError(f"Failed to load model: {e}")

        return self._model

    def unload_model(self) -> None:
        """Unload model from memory/VRAM"""
        if self._model is not None:
            print(f"Unloading Whisper model '{self.model_name}' from {self.device.upper()}...")
            del self._model
            self._model = None
            # Force garbage collection to free VRAM immediately
            import gc
            gc.collect()
            # If using CUDA, also clear CUDA cache
            if self.device == "cuda":
                try:
                    import torch
                    torch.cuda.empty_cache()
                    print("CUDA cache cleared")
                except ImportError:
                    pass

    def is_model_downloaded(self) -> bool:
        """Check if the Whisper model is already downloaded and cached"""
        from pathlib import Path

        # Check if model is already downloaded in HuggingFace cache
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        if not cache_dir.exists():
            return False

        # Look for model directory (format: models--Systran--faster-whisper-{model})
        # Special case: turbo is stored as faster-whisper-large-v3-turbo
        search_pattern = "faster-whisper-large-v3-turbo" if self.model_name == "turbo" else f"faster-whisper-{self.model_name}"
        for entry in cache_dir.iterdir():
            if search_pattern in entry.name:
                return True

        return False

    def validate_config(self) -> None:
        """Validate Whisper configuration"""
        # Just validate the model name is valid, don't load the model yet
        # Model will be loaded on first transcription
        available_models = self.get_available_models()
        if self.model_name not in available_models:
            raise ValueError(f"Invalid Whisper model '{self.model_name}'. Available models: {', '.join(available_models)}")

    def get_available_models(self) -> List[str]:
        """Return available Faster Whisper models"""
        return [
            "tiny",
            "base",
            "small",
            "medium",
            "large-v3",
            "turbo",
        ]

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using Faster Whisper.

        Args:
            audio_bytes: WAV format audio data
            language: ISO language code ('de', 'en') or None for auto-detect

        Returns:
            Transcribed text or None on error
        """
        try:
            # Create file-like object from bytes
            audio_buffer = io.BytesIO(audio_bytes)

            # Transcribe with language hint if provided
            transcribe_params = {}
            if language:
                transcribe_params['language'] = language

            segments, info = self.model.transcribe(
                audio_buffer,
                **transcribe_params
            )

            # Combine all segments into single transcript
            transcript_parts = [segment.text for segment in segments]
            transcript = " ".join(transcript_parts).strip()

            return transcript if transcript else None

        except (Exception, SystemError) as e:
            error_str = str(e).lower()
            if "cudnn" in error_str or "cuda" in error_str:
                print(f"CUDA/cuDNN error during transcription: {e}")
                print("Consider setting WHISPER_DEVICE=cpu in your config file (.env or voicesnip.ini)")
            else:
                print(f"Whisper transcription error: {e}")
            return None
