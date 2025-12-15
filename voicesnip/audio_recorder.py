"""
Audio Recording

Handles audio recording, streaming, and WAV conversion.
"""

import sys
import io
import wave
import threading
import numpy as np
import sounddevice as sd

from .constants import CHANNELS, DTYPE


class AudioRecorder:
    """Manages audio recording and streaming"""

    def __init__(self, device_id=None, sample_rate=16000):
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.is_recording = threading.Event()
        self.audio_data = []
        self.audio_data_lock = threading.Lock()
        self.stream = None

    def audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk"""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)
        if self.is_recording.is_set():
            with self.audio_data_lock:
                self.audio_data.append(indata.copy())

    def start_recording(self):
        """Start audio recording

        Raises:
            sd.PortAudioError: If device cannot be opened
            OSError: If device is unavailable
        """
        if self.is_recording.is_set():
            return

        self.is_recording.set()
        with self.audio_data_lock:
            self.audio_data = []

        # Start audio stream with selected device
        stream_params = {
            'samplerate': self.sample_rate,
            'channels': CHANNELS,
            'dtype': DTYPE,
            'callback': self.audio_callback
        }

        if self.device_id is not None:
            stream_params['device'] = self.device_id

        try:
            self.stream = sd.InputStream(**stream_params)
            self.stream.start()
        except (sd.PortAudioError, OSError) as e:
            self.is_recording.clear()
            # Ensure stream is closed if partially initialized
            if self.stream:
                try:
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None
            raise

    def stop_recording(self):
        """Stop recording and return whether audio data was captured"""
        if not self.is_recording.is_set():
            return False

        self.is_recording.clear()

        # Stop audio stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Check if we have audio data
        with self.audio_data_lock:
            has_audio = len(self.audio_data) > 0

        return has_audio

    def get_audio_wav_bytes(self):
        """Convert recorded audio data to WAV format bytes

        Returns:
            bytes: WAV format audio data
        """
        # Concatenate all audio chunks
        with self.audio_data_lock:
            audio_array = np.concatenate(self.audio_data, axis=0)

        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_array.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()

    def cleanup(self):
        """Clean up audio resources"""
        if self.is_recording.is_set():
            self.is_recording.clear()

        # Close audio stream
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
