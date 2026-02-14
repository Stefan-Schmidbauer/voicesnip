"""
Whisper ROCm Local STT Provider

Provides speech-to-text using Whisper with PyTorch ROCm for AMD GPUs.
Uses the transformers library (CTranslate2/faster-whisper is CUDA-only).
"""

import os
import io
import wave
import subprocess
from typing import Optional, List
from .base import STTProvider

# Map short model names to HuggingFace model IDs
MODEL_MAP = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large-v3": "openai/whisper-large-v3",
    "turbo": "openai/whisper-large-v3-turbo",
}

# Known GFX version overrides for GPU architectures not in official PyTorch ROCm builds.
# Maps actual gfx version to the closest supported version for HSA_OVERRIDE_GFX_VERSION.
# Official PyTorch ROCm 6.2 supports: gfx900, gfx906, gfx908, gfx90a, gfx942, gfx1030, gfx1100
GFX_OVERRIDE_MAP = {
    "gfx1150": "11.0.0",  # RDNA 3.5 Strix Point -> gfx1100
    "gfx1151": "11.0.0",  # RDNA 3.5 Strix Point -> gfx1100
    "gfx1101": "11.0.0",  # RDNA 3 (RX 7800/7700) -> gfx1100
    "gfx1102": "11.0.0",  # RDNA 3 (RX 7600) -> gfx1100
    "gfx1031": "10.3.0",  # RDNA 2 (RX 6700) -> gfx1030
    "gfx1032": "10.3.0",  # RDNA 2 (RX 6600) -> gfx1030
    "gfx1035": "10.3.0",  # RDNA 2 iGPU -> gfx1030
    "gfx1036": "10.3.0",  # RDNA 2 iGPU -> gfx1030
}


def _detect_gfx_version() -> Optional[str]:
    """Detect the GPU's GFX version via rocm-smi."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--showgfxversion"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line_lower = line.lower().strip()
                if "gfx" in line_lower:
                    # Extract gfxNNNN from the line
                    for word in line_lower.split():
                        if word.startswith("gfx"):
                            return word
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: try rocminfo
    try:
        result = subprocess.run(
            ["rocminfo"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Name:") and "gfx" in stripped.lower():
                    for word in stripped.split():
                        if word.lower().startswith("gfx"):
                            return word.lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _apply_gfx_override():
    """Auto-set HSA_OVERRIDE_GFX_VERSION if needed for unsupported GPU architectures."""
    # Don't override if user already set it
    if os.environ.get("HSA_OVERRIDE_GFX_VERSION"):
        return

    gfx = _detect_gfx_version()
    if not gfx:
        return

    override = GFX_OVERRIDE_MAP.get(gfx)
    if override:
        print(f"GPU architecture {gfx} detected — setting HSA_OVERRIDE_GFX_VERSION={override}")
        os.environ["HSA_OVERRIDE_GFX_VERSION"] = override


class WhisperROCmProvider(STTProvider):
    """Whisper ROCm local STT provider (AMD GPU via PyTorch ROCm)"""

    def __init__(self, model: Optional[str] = None, **kwargs):
        """
        Initialize Whisper ROCm provider.

        Args:
            model: Model size (tiny, base, small, medium, large-v3, turbo)
            **kwargs: Ignored (allows generic config forwarding)
        """
        self.model_name = model or os.getenv("WHISPER_MODEL", "small")
        self._pipeline = None

    @property
    def name(self) -> str:
        return "Whisper ROCm (Local)"

    def _get_hf_model_id(self) -> str:
        """Map short model name to HuggingFace model ID"""
        return MODEL_MAP.get(self.model_name, f"openai/whisper-{self.model_name}")

    @property
    def pipeline(self):
        """Lazy load pipeline on first use"""
        if self._pipeline is None:
            # Apply GFX override before importing torch (must be set before HIP init)
            _apply_gfx_override()

            import torch
            from transformers import pipeline as hf_pipeline

            model_id = self._get_hf_model_id()

            if not torch.cuda.is_available():
                raise ValueError(
                    "ROCm not available. Ensure PyTorch ROCm is installed:\n"
                    "pip install torch torchaudio --index-url https://download.pytorch.org/whl/rocm6.2"
                )

            gpu_name = torch.cuda.get_device_name(0)
            print(f"ROCm GPU: {gpu_name}")

            # Check if model is already cached
            if self.is_model_downloaded():
                print(f"Loading Whisper model '{self.model_name}' on ROCm GPU...")
            else:
                print(f"Downloading Whisper model '{self.model_name}'...")
                print("(Larger models can take a long time - please be patient)")

            try:
                self._pipeline = hf_pipeline(
                    "automatic-speech-recognition",
                    model=model_id,
                    torch_dtype=torch.float16,
                    device="cuda",  # ROCm uses CUDA API via HIP
                )
                print(f"Model '{self.model_name}' ready on ROCm GPU!")
            except (Exception, SystemError) as e:
                error_str = str(e).lower()
                if "invalid device function" in error_str or "hip error" in error_str:
                    gfx = _detect_gfx_version() or "unknown"
                    raise ValueError(
                        f"GPU architecture {gfx} not supported by installed PyTorch ROCm.\n"
                        f"Try setting: export HSA_OVERRIDE_GFX_VERSION=11.0.0\n"
                        f"Or check: https://rocm.docs.amd.com/en/latest/reference/gpu-arch-specs.html"
                    )
                if "rocm" in error_str or "hip" in error_str or "cuda" in error_str:
                    raise ValueError(f"ROCm GPU error: {e}")
                raise ValueError(f"Failed to load model: {e}")

        return self._pipeline

    def unload_model(self) -> None:
        """Unload model from VRAM"""
        if self._pipeline is not None:
            print(f"Unloading Whisper model '{self.model_name}' from ROCm GPU...")
            del self._pipeline
            self._pipeline = None
            import gc
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except ImportError:
                pass

    def is_model_downloaded(self) -> bool:
        """Check if the Whisper model is already downloaded in HuggingFace cache"""
        from pathlib import Path

        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        if not cache_dir.exists():
            return False

        hf_model_id = self._get_hf_model_id()
        # HuggingFace cache format: models--openai--whisper-small
        cache_name = "models--" + hf_model_id.replace("/", "--")
        return (cache_dir / cache_name).exists()

    def validate_config(self) -> None:
        """Validate ROCm Whisper configuration"""
        available_models = self.get_available_models()
        if self.model_name not in available_models:
            raise ValueError(f"Invalid model '{self.model_name}'. Available: {', '.join(available_models)}")

    def get_available_models(self) -> List[str]:
        """Return available Whisper models"""
        return list(MODEL_MAP.keys())

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using Whisper on ROCm GPU.

        Args:
            audio_bytes: WAV format audio data
            language: ISO language code ('de', 'en') or None for auto-detect

        Returns:
            Transcribed text or None on error
        """
        try:
            import numpy as np

            # Parse WAV bytes to numpy array
            wav_buffer = io.BytesIO(audio_bytes)
            with wave.open(wav_buffer, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                n_frames = wav_file.getnframes()
                audio_data = wav_file.readframes(n_frames)
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

            generate_kwargs = {}
            if language:
                generate_kwargs["language"] = language

            result = self.pipeline(
                {"raw": audio_np, "sampling_rate": sample_rate},
                generate_kwargs=generate_kwargs,
            )

            transcript = result.get("text", "").strip()
            return transcript if transcript else None

        except Exception as e:
            error_str = str(e).lower()
            if "invalid device function" in error_str or "hip error" in error_str:
                gfx = _detect_gfx_version() or "unknown"
                raise RuntimeError(
                    f"GPU architecture {gfx} not supported. "
                    f"Set HSA_OVERRIDE_GFX_VERSION=11.0.0 and restart."
                )
            if "rocm" in error_str or "hip" in error_str or "cuda" in error_str:
                raise RuntimeError(f"ROCm GPU error: {e}")
            raise RuntimeError(f"Whisper ROCm transcription error: {e}")
