"""
Whisper Vulkan Local STT Provider

Provides speech-to-text using whisper.cpp (via pywhispercpp) on any GPU with a
Vulkan driver. Intended for integrated GPUs (AMD Radeon 780M/880M/890M, Intel
Arc), where CTranslate2/faster-whisper has no backend and ROCm is unreliable.
"""

import os
import io
import sys
import wave
from pathlib import Path
from typing import Optional, List
from .base import STTProvider

# Map short model names to whisper.cpp ggml model names.
# The large models use q5_0 quantization: half the memory (an iGPU shares
# system RAM); for turbo the transcript matched f16 and ran faster on a
# Radeon 780M.
MODEL_MAP = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large-v3": "large-v3-q5_0",
    "turbo": "large-v3-turbo-q5_0",
}

# Silero VAD model for whisper.cpp (~0.9 MB), downloaded on first use
VAD_MODEL_NAME = "ggml-silero-v6.2.0.bin"
VAD_MODEL_URL = f"https://huggingface.co/ggml-org/whisper-vad/resolve/main/{VAD_MODEL_NAME}"

WHISPER_SAMPLE_RATE = 16000


GGML_LOG_LEVEL_WARN = 3
GGML_LOG_LEVEL_CONT = 5  # continues the previous message
_last_log_level = 0


def _whispercpp_log(level: int, text: str) -> None:
    """Forward only warnings and errors from whisper.cpp/ggml.

    whisper.cpp logs a dozen INFO lines per transcription (VAD segments,
    language detection), which would flood the console.
    """
    global _last_log_level
    if level != GGML_LOG_LEVEL_CONT:
        _last_log_level = level
    if _last_log_level >= GGML_LOG_LEVEL_WARN:
        sys.stderr.write(text)


def _models_dir() -> Path:
    """pywhispercpp's model directory (platformdirs user_data_dir on Linux)."""
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "pywhispercpp" / "models"


class WhisperVulkanProvider(STTProvider):
    """Whisper Vulkan local STT provider (any GPU via whisper.cpp + Vulkan)"""

    def __init__(self, model: Optional[str] = None, gpu_device: Optional[str] = None, **kwargs):
        """
        Initialize Whisper Vulkan provider.

        Args:
            model: Model size (tiny, base, small, medium, large-v3, turbo)
            gpu_device: Vulkan device index; falls back to $VOICESNIP_VULKAN_DEVICE, then 0
            **kwargs: Ignored (allows generic config forwarding)
        """
        self.model_name = model or os.getenv("WHISPER_MODEL", "small")
        self.gpu_device = int(gpu_device if gpu_device is not None
                              else os.getenv("VOICESNIP_VULKAN_DEVICE", "0"))
        self._model = None

    @property
    def name(self) -> str:
        return "Whisper Vulkan (Local)"

    def _get_ggml_model_name(self) -> str:
        """Map short model name to whisper.cpp ggml model name"""
        return MODEL_MAP.get(self.model_name, self.model_name)

    def _get_vad_model_path(self) -> Optional[str]:
        """Return the VAD model path, downloading it on first use.

        Without VAD a recording with no speech in it is not returned empty:
        Whisper invents text for silence (see WhisperProvider.transcribe).
        Returns None if the download fails; transcription then runs without VAD.
        """
        path = _models_dir() / VAD_MODEL_NAME
        if path.is_file():
            return str(path)

        try:
            import requests

            print("Downloading VAD model...")
            path.parent.mkdir(parents=True, exist_ok=True)
            response = requests.get(VAD_MODEL_URL, timeout=60)
            response.raise_for_status()
            tmp_path = path.with_suffix(".part")
            tmp_path.write_bytes(response.content)
            tmp_path.rename(path)
            return str(path)
        except Exception as e:
            print(f"Warning: Could not download VAD model ({e}) - continuing without VAD")
            return None

    @property
    def model(self):
        """Lazy load model on first use"""
        if self._model is None:
            try:
                import _pywhispercpp
                from pywhispercpp.model import Model
            except ImportError as e:
                raise ValueError(
                    f"pywhispercpp with Vulkan is not available ({e}).\n"
                    "Reinstall VoiceSnip with the 'vulkan' profile:\n"
                    "./install.py --profile vulkan"
                )

            _pywhispercpp.whisper_log_set(_whispercpp_log)

            if self.is_model_downloaded():
                print(f"Loading Whisper model '{self.model_name}' on Vulkan device {self.gpu_device}...")
            else:
                print(f"Downloading Whisper model '{self.model_name}'...")
                print("(Larger models can take a long time - please be patient)")

            params = {
                "n_threads": min(8, max(1, (os.cpu_count() or 4) // 2)),
                "print_progress": False,
                "print_realtime": False,
            }
            vad_model_path = self._get_vad_model_path()
            if vad_model_path:
                params["vad"] = True
                params["vad_model_path"] = vad_model_path

            try:
                # Greedy decoding (pywhispercpp default): about a third faster
                # than beam search (size 5) on a Radeon 780M, with a transcript
                # of the same quality in our tests.
                self._model = Model(
                    self._get_ggml_model_name(),
                    context_params={"use_gpu": True, "gpu_device": self.gpu_device},
                    **params,
                )
                print(f"Model '{self.model_name}' ready on Vulkan device {self.gpu_device}!")
            except (Exception, SystemError) as e:
                raise ValueError(f"Failed to load model on Vulkan: {e}")

        return self._model

    def unload_model(self) -> None:
        """Unload model from GPU memory"""
        if self._model is not None:
            print(f"Unloading Whisper model '{self.model_name}' from Vulkan device {self.gpu_device}...")
            del self._model
            self._model = None
            import gc
            gc.collect()

    def is_model_downloaded(self) -> bool:
        """Check if the ggml model file is already in pywhispercpp's model directory"""
        return (_models_dir() / f"ggml-{self._get_ggml_model_name()}.bin").is_file()

    def validate_config(self) -> None:
        """Validate Vulkan Whisper configuration"""
        available_models = self.get_available_models()
        if self.model_name not in available_models:
            raise ValueError(f"Invalid model '{self.model_name}'. Available: {', '.join(available_models)}")

    def get_available_models(self) -> List[str]:
        """Return available Whisper models"""
        return list(MODEL_MAP.keys())

    def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
        """
        Transcribe audio using whisper.cpp on a Vulkan GPU.

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

            # whisper.cpp expects 16 kHz and does not resample; the recorder
            # falls back to 44.1/48 kHz on devices that reject 16 kHz.
            if sample_rate != WHISPER_SAMPLE_RATE and len(audio_np) > 0:
                n_out = int(len(audio_np) * WHISPER_SAMPLE_RATE / sample_rate)
                audio_np = np.interp(
                    np.linspace(0, len(audio_np) - 1, n_out),
                    np.arange(len(audio_np)),
                    audio_np,
                ).astype(np.float32)

            # pywhispercpp maps "" to auto-detect ("auto" works too but logs
            # "unknown language" on every call)
            segments = self.model.transcribe(audio_np, language=language or "")

            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            return transcript if transcript else None

        except (Exception, SystemError) as e:
            raise RuntimeError(f"Whisper Vulkan transcription error: {e}")
