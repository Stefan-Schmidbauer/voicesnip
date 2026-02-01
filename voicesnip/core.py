"""
VoiceSnip Core

Core functionality orchestrating audio recording, transcription,
and hotkey management.
"""

import threading
import sounddevice as sd

from .constants import DEFAULT_HOTKEY
from .audio_recorder import AudioRecorder
from .hotkey_manager import HotkeyManager
from .text_inserter import insert_text


class VoiceSnipCore:
    """Core functionality for audio recording and transcription"""

    def __init__(self, device_id=None, language='de', sample_rate=16000, hotkey=DEFAULT_HOTKEY,
                 provider_name='whisper', provider_config=None):
        self.language = language
        self.status_callback = None
        self.text_callback = None  # Callback for transcribed text
        self._shutting_down = threading.Event()

        # Initialize audio recorder
        self.audio_recorder = AudioRecorder(device_id=device_id, sample_rate=sample_rate)

        # Initialize hotkey manager
        self.hotkey_manager = HotkeyManager(hotkey_str=hotkey)

        # Processing thread reference (protected by _processing_lock)
        self.processing_thread = None
        self._processing_lock = threading.Lock()

        # Initialize provider dynamically
        from providers import create_provider
        provider_config = provider_config or {}
        self.stt_provider = create_provider(provider_name, **provider_config)
        self.stt_provider.validate_config()

    def set_status_callback(self, callback):
        """Set callback function for status updates"""
        self.status_callback = callback

    def set_text_callback(self, callback):
        """Set callback function for transcribed text"""
        self.text_callback = callback

    def notify_text(self, text):
        """Notify listeners about transcribed text"""
        if self.text_callback and not self._shutting_down.is_set():
            try:
                self.text_callback(text)
            except Exception:
                # Callback failed (e.g., GUI destroyed), ignore
                pass

    def update_status(self, message):
        """Update status via callback"""
        if self.status_callback and not self._shutting_down.is_set():
            try:
                self.status_callback(message)
            except Exception:
                # Callback failed (e.g., GUI destroyed), ignore
                pass

    def start_recording(self):
        """Start audio recording"""
        if self.audio_recorder.is_recording.is_set():
            return

        self.update_status("🎤 Recording...")

        try:
            self.audio_recorder.start_recording()
        except (sd.PortAudioError, OSError) as e:
            error_msg = str(e)
            if "Invalid number of channels" in error_msg or "Invalid sample rate" in error_msg:
                self.update_status(f"❌ Device configuration error")
            elif "Device unavailable" in error_msg or "busy" in error_msg.lower():
                self.update_status(f"❌ Device already in use")
            else:
                self.update_status(f"❌ Error opening microphone")
            print(f"Error opening device: {e}")
            return

    def stop_recording(self):
        """Stop recording and transcribe"""
        has_audio = self.audio_recorder.stop_recording()

        if not has_audio:
            self.update_status("⚠️ No audio data recorded")
            return

        self.update_status("⏳ Processing...")

        # Check if a previous processing is still running
        with self._processing_lock:
            if self.processing_thread and self.processing_thread.is_alive():
                self.update_status("⚠️ Previous recording still processing")
                return

            # Process in separate thread to not block GUI
            # Non-daemon thread to ensure transcription completes
            self.processing_thread = threading.Thread(target=self._process_audio)
            self.processing_thread.daemon = False
            self.processing_thread.start()

    def _process_audio(self):
        """Process audio in background thread"""
        try:
            # Convert audio data to WAV format
            audio_bytes = self.audio_recorder.get_audio_wav_bytes()

            # Transcribe
            try:
                text = self.transcribe(audio_bytes)

                if text:
                    self.update_status("✅ Transcription complete")
                    self.notify_text(text)
                    insert_text(text)
                else:
                    self.update_status("❌ No text recognized")
            except ValueError as e:
                # Authentication/configuration errors (invalid API key, etc.)
                self.update_status(f"❌ Configuration error: {str(e)}")
            except RuntimeError as e:
                # API or network errors
                self.update_status(f"❌ API error: {str(e)}")
            except Exception as e:
                # Catch-all for unexpected errors
                self.update_status(f"❌ Error: {str(e)}")
        finally:
            # Clear thread reference when done
            with self._processing_lock:
                self.processing_thread = None

    def transcribe(self, audio_bytes):
        """Send audio to configured STT provider and get transcription"""
        return self.stt_provider.transcribe(audio_bytes, self.language)

    def cleanup(self):
        """Clean up all resources (streams, threads)"""
        self._shutting_down.set()

        # Clean up audio recorder
        self.audio_recorder.cleanup()

        # Wait for processing thread to finish (with timeout)
        with self._processing_lock:
            thread = self.processing_thread
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

    def on_press(self, key):
        """Handle key press events"""
        self.hotkey_manager.on_press(key)

        # Start recording if hotkey combination is complete
        if self.hotkey_manager.is_hotkey_pressed() and not self.audio_recorder.is_recording.is_set():
            self.start_recording()

    def on_release(self, key):
        """Handle key release events"""
        self.hotkey_manager.on_release(key)

        # Stop recording if we were recording and released any part of the hotkey
        if self.audio_recorder.is_recording.is_set():
            if self.hotkey_manager.is_hotkey_part_released(key):
                self.stop_recording()
