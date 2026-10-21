"""
Audio helpers shared by the STT providers.
"""

import io
import wave

import numpy as np

WHISPER_SAMPLE_RATE = 16000


def wav_to_whisper_input(audio_bytes: bytes) -> np.ndarray:
    """Decode mono 16-bit WAV bytes to float32 samples at 16 kHz.

    Whisper models expect 16 kHz; the recorder falls back to 44.1/48 kHz on
    devices that reject 16 kHz, so other rates are resampled (linear
    interpolation is sufficient for speech).

    Decoding here instead of passing a file to faster-whisper also keeps its
    PyAV decoder out of the path: PyAV 19 dropped the `metadata_errors`
    argument that faster-whisper 1.2.1 passes to `av.open()`.
    """
    with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        audio_data = wav_file.readframes(wav_file.getnframes())

    audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    if sample_rate != WHISPER_SAMPLE_RATE and len(audio) > 0:
        n_out = int(len(audio) * WHISPER_SAMPLE_RATE / sample_rate)
        audio = np.interp(
            np.linspace(0, len(audio) - 1, n_out),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)

    return audio
