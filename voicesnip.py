#!/usr/bin/env python3
"""
VoiceSnip GUI - Push-to-Talk Speech-to-Text

Simple GUI for selecting microphone, language, provider, and hotkey.
Press and hold your configured hotkey (default: Ctrl+Space) to record audio.
Release to transcribe and insert text into the active application.

Speech-to-Text Providers:
- Whisper (Local, Free): Local processing using Faster Whisper
- Deepgram (Cloud): Cloud API with punctuation and smart formatting

Features:
- Configurable hotkey (e.g., Ctrl+Space, Alt+R, Ctrl+Shift+V)
- Multiple STT provider support (Whisper, Deepgram)
- Automatic terminal detection for better paste support
- Settings persistence

Copyright (c) 2025 Stefan Schmidbauer
License: MIT License
GitHub: https://github.com/Stefan-Schmidbauer/voicesnip
"""

import os
import sys
import io
import wave
import json
import threading
import webbrowser
import subprocess
import time
import re
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from configparser import ConfigParser
from PIL import Image, ImageTk

import numpy as np
import sounddevice as sd
from pynput import keyboard
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TARGET_SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Use XDG standard config directory
CONFIG_DIR = Path.home() / '.config' / 'voicesnip'
CONFIG_FILE = CONFIG_DIR / 'config.json'

# Common sample rates to try (in order of preference)
COMMON_SAMPLE_RATES = [16000, 44100, 48000, 22050, 8000]

# GitHub URL
GITHUB_URL = "https://github.com/Stefan-Schmidbauer/voicesnip"

# Terminal detection keywords (frozenset for O(1) lookup)
TERMINAL_KEYWORDS = frozenset([
    'terminal',
    'konsole',
    'gnome-terminal',
    'xterm',
    'rxvt',
    'urxvt',
    'kitty',
    'alacritty',
    'terminator',
    'tilix',
    'terminology',
    'guake',
    'yakuake',
    'qterminal',
    'lxterminal',
    'mate-terminal',
    'xfce4-terminal',
    'wezterm',
    'st',  # simple terminal
    'foot',
    'contour',
])

# Key mapping constants for hotkey parsing
KEY_MAP = {
    'ctrl': keyboard.Key.ctrl,
    'control': keyboard.Key.ctrl,
    'alt': keyboard.Key.alt,
    'shift': keyboard.Key.shift,
    'cmd': keyboard.Key.cmd,
    'super': keyboard.Key.cmd,
    'space': keyboard.Key.space,
    'enter': keyboard.Key.enter,
    'tab': keyboard.Key.tab,
    'esc': keyboard.Key.esc,
    'escape': keyboard.Key.esc,
    # Function keys
    'f1': keyboard.Key.f1,
    'f2': keyboard.Key.f2,
    'f3': keyboard.Key.f3,
    'f4': keyboard.Key.f4,
    'f5': keyboard.Key.f5,
    'f6': keyboard.Key.f6,
    'f7': keyboard.Key.f7,
    'f8': keyboard.Key.f8,
    'f9': keyboard.Key.f9,
    'f10': keyboard.Key.f10,
    'f11': keyboard.Key.f11,
    'f12': keyboard.Key.f12,
}

KEY_NAME_MAP = {
    keyboard.Key.ctrl: 'ctrl',
    keyboard.Key.ctrl_l: 'ctrl',
    keyboard.Key.ctrl_r: 'ctrl',
    keyboard.Key.alt: 'alt',
    keyboard.Key.alt_l: 'alt',
    keyboard.Key.alt_r: 'alt',
    keyboard.Key.shift: 'shift',
    keyboard.Key.shift_l: 'shift',
    keyboard.Key.shift_r: 'shift',
    keyboard.Key.cmd: 'cmd',
    keyboard.Key.cmd_l: 'cmd',
    keyboard.Key.cmd_r: 'cmd',
    keyboard.Key.space: 'space',
    keyboard.Key.enter: 'enter',
    keyboard.Key.tab: 'tab',
    keyboard.Key.esc: 'esc',
    # Function keys
    keyboard.Key.f1: 'f1',
    keyboard.Key.f2: 'f2',
    keyboard.Key.f3: 'f3',
    keyboard.Key.f4: 'f4',
    keyboard.Key.f5: 'f5',
    keyboard.Key.f6: 'f6',
    keyboard.Key.f7: 'f7',
    keyboard.Key.f8: 'f8',
    keyboard.Key.f9: 'f9',
    keyboard.Key.f10: 'f10',
    keyboard.Key.f11: 'f11',
    keyboard.Key.f12: 'f12',
}

# Language mapping constants
LANGUAGE_CODE_TO_INDEX = {'de': 0, 'en': 1, '': 2}
LANGUAGE_INDEX_TO_CODE = {0: 'de', 1: 'en', 2: ''}

# Default hotkey
DEFAULT_HOTKEY = "ctrl+space"




class VoiceSnipCore:
    """Core functionality for audio recording and transcription"""

    def __init__(self, device_id=None, language='de', sample_rate=16000, hotkey=DEFAULT_HOTKEY,
                 provider_name='whisper', provider_config=None):
        self.is_recording = threading.Event()
        self.audio_data = []
        self.audio_data_lock = threading.Lock()
        self.stream = None
        self.processing_thread = None
        self.device_id = device_id
        self.language = language
        self.sample_rate = sample_rate  # Actual recording sample rate
        self.status_callback = None
        self._shutting_down = False

        # Parse hotkey configuration
        self.hotkey_config = self.parse_hotkey(hotkey)
        self.pressed_keys = set()
        self.pressed_keys_lock = threading.Lock()

        # Initialize provider dynamically
        from providers import create_provider
        provider_config = provider_config or {}
        self.stt_provider = create_provider(provider_name, **provider_config)
        self.stt_provider.validate_config()

    def parse_hotkey(self, hotkey_str):
        """Parse hotkey string (e.g., 'ctrl+space') into key components

        Raises:
            ValueError: If hotkey string is empty or invalid
        """
        # Validate hotkey is not empty
        if not hotkey_str or not hotkey_str.strip():
            raise ValueError("Hotkey cannot be empty")

        parts = [k.strip().lower() for k in hotkey_str.split('+') if k.strip()]

        # Validate we have at least one key after filtering
        if not parts:
            raise ValueError("Invalid hotkey format")

        config = {
            'modifiers': [],
            'trigger_key': None,
            'raw': hotkey_str
        }

        # Use module-level KEY_MAP constant
        for part in parts:
            if part in ['ctrl', 'control', 'alt', 'shift', 'cmd', 'super']:
                config['modifiers'].append(KEY_MAP[part])
            else:
                # Trigger key (last non-modifier key)
                if part in KEY_MAP:
                    config['trigger_key'] = KEY_MAP[part]
                else:
                    # Single character key
                    try:
                        config['trigger_key'] = keyboard.KeyCode.from_char(part)
                    except (ValueError, AttributeError):
                        config['trigger_key'] = part

        # Validate that we have a trigger key
        if config['trigger_key'] is None:
            raise ValueError(f"Invalid hotkey: no trigger key found in '{hotkey_str}'")

        return config

    def set_status_callback(self, callback):
        """Set callback function for status updates"""
        self.status_callback = callback

    def update_status(self, message):
        """Update status via callback"""
        if self.status_callback and not self._shutting_down:
            try:
                self.status_callback(message)
            except Exception:
                # Callback failed (e.g., GUI destroyed), ignore
                pass

    def audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk"""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)
        if self.is_recording.is_set():
            with self.audio_data_lock:
                self.audio_data.append(indata.copy())

    def start_recording(self):
        """Start audio recording"""
        if self.is_recording.is_set():
            return

        self.update_status("🎤 Recording...")
        self.is_recording.set()
        with self.audio_data_lock:
            self.audio_data = []

        # Start audio stream with selected device
        stream_params = {
            'samplerate': self.sample_rate,  # Use device's sample rate
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

            error_msg = str(e)
            if "Invalid number of channels" in error_msg or "Invalid sample rate" in error_msg:
                self.update_status(f"❌ Device configuration error")
            elif "Device unavailable" in error_msg or "busy" in error_msg.lower():
                self.update_status(f"❌ Device already in use")
            else:
                self.update_status(f"❌ Error opening microphone")
            print(f"Error opening device {self.device_id}: {e}")
            return

    def stop_recording(self):
        """Stop recording and transcribe"""
        if not self.is_recording.is_set():
            return

        self.is_recording.clear()

        # Stop audio stream
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        # Check if we have audio data
        with self.audio_data_lock:
            has_audio = len(self.audio_data) > 0

        if not has_audio:
            self.update_status("⚠️ No audio data recorded")
            return

        self.update_status("⏳ Processing...")

        # Check if a previous processing is still running
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
            audio_bytes = self.create_wav_bytes()

            # Transcribe
            try:
                text = self.transcribe(audio_bytes)

                if text:
                    self.update_status(f"✅ Transcribed: {text}")
                    self.insert_text(text)
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
            self.processing_thread = None

    def create_wav_bytes(self):
        """Convert recorded audio data to WAV format bytes"""
        # Concatenate all audio chunks
        with self.audio_data_lock:
            audio_array = np.concatenate(self.audio_data, axis=0)

        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.sample_rate)  # Use actual recording sample rate
            wav_file.writeframes(audio_array.tobytes())

        wav_buffer.seek(0)
        return wav_buffer.read()

    def transcribe(self, audio_bytes):
        """Send audio to configured STT provider and get transcription"""
        return self.stt_provider.transcribe(audio_bytes, self.language)

    def cleanup(self):
        """Clean up all resources (streams, threads)"""
        self._shutting_down = True

        # Stop recording if active
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

        # Wait for processing thread to finish (with timeout)
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2.0)

    def insert_text(self, text):
        """Insert text into active application using xclip + xdotool"""
        try:
            # Copy text to both clipboard and primary selection
            # Clipboard for Ctrl+V / Ctrl+Shift+V
            with subprocess.Popen(
                ['xclip', '-selection', 'clipboard'],
                stdin=subprocess.PIPE
            ) as process:
                process.communicate(text.encode('utf-8'), timeout=2.0)

            # Primary selection for middle-click paste
            with subprocess.Popen(
                ['xclip', '-selection', 'primary'],
                stdin=subprocess.PIPE
            ) as process:
                process.communicate(text.encode('utf-8'), timeout=2.0)

            # Small delay to ensure clipboard is set
            time.sleep(0.1)

            # Detect if active window is a terminal
            is_terminal = self.is_terminal_window()

            # Use appropriate paste method
            if is_terminal:
                # For terminals: type text directly (more reliable)
                # xdotool type simulates typing each character
                subprocess.run(
                    ['xdotool', 'type', '--clearmodifiers', '--', text],
                    check=True,
                    timeout=5.0
                )
            else:
                # For regular applications: use Ctrl+V (faster)
                subprocess.run(
                    ['xdotool', 'key', '--clearmodifiers', 'ctrl+v'],
                    check=True,
                    timeout=2.0
                )

        except subprocess.TimeoutExpired:
            print("Error: Clipboard operation timed out")
        except subprocess.CalledProcessError as e:
            print(f"Error inserting text: {e}")
        except FileNotFoundError:
            print("xclip or xdotool not found. Please install: sudo apt install xclip xdotool")

    def is_terminal_window(self):
        """Detect if the active window is a terminal emulator"""
        try:
            # Get active window ID
            result = subprocess.run(
                ['xdotool', 'getactivewindow'],
                capture_output=True,
                text=True,
                check=True,
                timeout=2.0
            )
            window_id = result.stdout.strip()

            # Validate window_id is numeric to prevent command injection
            if not window_id.isdigit():
                return False

            # Get active window name
            result = subprocess.run(
                ['xdotool', 'getactivewindow', 'getwindowname'],
                capture_output=True,
                text=True,
                check=True,
                timeout=2.0
            )
            window_name_lower = result.stdout.lower().strip()

            # Get window class using xprop (xdotool doesn't have getwindowclassname)
            result_class = subprocess.run(
                ['xprop', '-id', window_id, 'WM_CLASS'],
                capture_output=True,
                text=True,
                check=True,
                timeout=2.0
            )
            window_class_lower = result_class.stdout.lower().strip()

            # Check if any terminal keyword is in window name or class
            # Using frozenset from module constants for O(1) lookup
            for keyword in TERMINAL_KEYWORDS:
                if keyword in window_name_lower or keyword in window_class_lower:
                    return True

            return False

        except subprocess.CalledProcessError:
            # If detection fails, assume not a terminal
            return False

    def normalize_key(self, key):
        """Normalize key to handle left/right variants of modifier keys"""
        # Map left/right variants to generic form
        key_mapping = {
            keyboard.Key.ctrl_l: keyboard.Key.ctrl,
            keyboard.Key.ctrl_r: keyboard.Key.ctrl,
            keyboard.Key.alt_l: keyboard.Key.alt,
            keyboard.Key.alt_r: keyboard.Key.alt,
            keyboard.Key.shift_l: keyboard.Key.shift,
            keyboard.Key.shift_r: keyboard.Key.shift,
            keyboard.Key.cmd_l: keyboard.Key.cmd,
            keyboard.Key.cmd_r: keyboard.Key.cmd,
        }
        return key_mapping.get(key, key)

    def is_hotkey_pressed(self):
        """Check if the configured hotkey combination is currently pressed"""
        with self.pressed_keys_lock:
            # Check if all modifiers are pressed
            for modifier in self.hotkey_config['modifiers']:
                if modifier not in self.pressed_keys:
                    return False

            # Check if trigger key is pressed
            trigger_key = self.hotkey_config['trigger_key']

            # For KeyCode objects (character keys), compare by char value (case-insensitive)
            if isinstance(trigger_key, keyboard.KeyCode):
                # Get the expected char value (lowercase)
                expected_char = trigger_key.char.lower() if trigger_key.char else None

                # Check if any pressed key has the same char value
                for pressed_key in self.pressed_keys:
                    if isinstance(pressed_key, keyboard.KeyCode) and pressed_key.char:
                        # Compare case-insensitive
                        if pressed_key.char.lower() == expected_char:
                            return True
                return False
            else:
                # For special keys (Key.space, Key.ctrl, etc.), use direct comparison
                if trigger_key not in self.pressed_keys:
                    return False

            return True

    def on_press(self, key):
        """Handle key press events"""
        normalized_key = self.normalize_key(key)
        with self.pressed_keys_lock:
            self.pressed_keys.add(normalized_key)
            # Also add the original key (for character keys)
            self.pressed_keys.add(key)

        # Start recording if hotkey combination is complete
        if self.is_hotkey_pressed() and not self.is_recording.is_set():
            self.start_recording()

    def on_release(self, key):
        """Handle key release events"""
        normalized_key = self.normalize_key(key)

        # Remove from pressed keys
        with self.pressed_keys_lock:
            self.pressed_keys.discard(normalized_key)
            self.pressed_keys.discard(key)

        # Stop recording if we were recording and released any part of the hotkey
        if self.is_recording.is_set():
            # Check if any required key was released
            trigger_key = self.hotkey_config['trigger_key']
            all_hotkey_keys = set(self.hotkey_config['modifiers']) | {trigger_key}

            # Check if the released key is part of the hotkey
            is_hotkey_part = False
            if normalized_key in all_hotkey_keys or key in all_hotkey_keys:
                is_hotkey_part = True
            # For KeyCode objects, compare by char value (case-insensitive)
            elif isinstance(trigger_key, keyboard.KeyCode) and isinstance(key, keyboard.KeyCode):
                if trigger_key.char and key.char:
                    if key.char.lower() == trigger_key.char.lower():
                        is_hotkey_part = True

            if is_hotkey_part:
                self.stop_recording()


class VoiceSnipGUI:
    """Tkinter GUI for VoiceSnip"""

    def __init__(self, root, installation_config):
        self.root = root
        self.root.title("VoiceSnip")

        self.core = None
        self.listener = None
        self.is_active = False

        # Store installation config
        self.installation_config = installation_config
        self.features = installation_config['features']

        # Load config
        self.config = self.load_config()

        # Set window size (either from saved config or default)
        self.apply_window_size()
        self.root.resizable(True, True)

        # Bind window resize event to save size
        self.root.bind('<Configure>', self.on_window_configure)
        self._resize_after_id = None

        # Create UI
        self.create_widgets()

        # Populate devices
        self.populate_devices()

        # Load saved settings
        self.load_settings()

    def scale_window_size(self, base_width, base_height):
        """Scale window size based on system DPI"""
        try:
            # Get DPI scaling factor
            # Tkinter returns pixels per inch (DPI)
            # Standard DPI is 96, so scaling_factor = current_dpi / 96
            dpi = self.root.winfo_fpixels('1i')  # Get DPI (pixels per inch)
            scaling_factor = dpi / 96.0

            # Apply scaling factor with minimum of 1.0
            scaling_factor = max(1.0, scaling_factor)

            scaled_width = int(base_width * scaling_factor)
            scaled_height = int(base_height * scaling_factor)

            return scaled_width, scaled_height
        except Exception as e:
            # Fallback to base size if scaling detection fails
            print(f"Could not detect DPI scaling: {e}")
            return base_width, base_height

    def apply_window_size(self):
        """Apply window size from config or use default"""
        if 'window_width' in self.config and 'window_height' in self.config:
            # Use saved window size
            width = self.config['window_width']
            height = self.config['window_height']
        else:
            # Calculate default size based on DPI scaling
            base_width, base_height = 600, 800
            width, height = self.scale_window_size(base_width, base_height)

        self.root.geometry(f"{width}x{height}")

    def on_window_configure(self, event):
        """Handle window resize/move events"""
        # Only handle events for the root window, not child widgets
        if event.widget != self.root:
            return

        # Debounce: only save after user stops resizing for 500ms
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)

        self._resize_after_id = self.root.after(500, self.save_window_size)

    def save_window_size(self):
        """Save current window size to config"""
        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            # Only save if values are reasonable (not minimized, etc.)
            if width > 100 and height > 100:
                self.config['window_width'] = width
                self.config['window_height'] = height
                self.save_config()
        except tk.TclError:
            # Window was destroyed, ignore
            pass

    def create_widgets(self):
        """Create GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Logo
        logo_frame = ttk.Frame(main_frame)
        logo_frame.pack(pady=(0, 20))

        try:
            # Load PNG logo
            png_path = os.path.join(os.path.dirname(__file__), "assets", "icons", "app", "voicesnip_icon.png")
            if os.path.exists(png_path):
                image = Image.open(png_path)
                photo = ImageTk.PhotoImage(image)

                logo_label = ttk.Label(logo_frame, image=photo)
                logo_label.image = photo  # Keep reference
                logo_label.pack()

                # Close PIL image after PhotoImage is created
                image.close()
        except Exception as e:
            # Fallback to text title if logo fails
            print(f"Could not load logo: {e}")
            title_label = ttk.Label(logo_frame, text="VoiceSnip", font=("Arial", 16, "bold"))
            title_label.pack()

        # Microphone selection
        mic_frame = ttk.LabelFrame(main_frame, text="Microphone", padding="10")
        mic_frame.pack(fill=tk.X, pady=(0, 10))

        self.mic_combo = ttk.Combobox(mic_frame, state="readonly", width=50)
        self.mic_combo.pack(fill=tk.X)

        # Provider selection (combines provider type and device)
        provider_frame = ttk.LabelFrame(main_frame, text="Provider", padding="10")
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        self.provider_combo = ttk.Combobox(provider_frame, state="readonly", width=50)

        # Build provider list dynamically based on installation features
        self.provider_display_to_name = {}  # Map display names to internal names
        providers = []

        # Check for Whisper features
        if 'whisper' in self.features:
            display_name = "Whisper Local CPU (Free)"
            providers.append(display_name)
            self.provider_display_to_name[display_name] = "whisper-local-cpu"

            # Check for GPU features
            if 'cuda' in self.features:
                display_name = "Whisper Local GPU (Free, CUDA)"
                providers.append(display_name)
                self.provider_display_to_name[display_name] = "whisper-local-gpu"

        # Deepgram is always available (cloud-based)
        if 'deepgram' in self.features:
            display_name = "Deepgram Cloud (API Key required)"
            providers.append(display_name)
            self.provider_display_to_name[display_name] = "deepgram-cloud"

        self.provider_combo['values'] = tuple(providers)
        if providers:
            self.provider_combo.current(0)
        else:
            # Should never happen with proper installation
            messagebox.showerror("Configuration Error",
                               "No providers available. Please reinstall VoiceSnip.")
            sys.exit(1)
        self.provider_combo.bind('<<ComboboxSelected>>', lambda e: self.on_provider_changed())
        self.provider_combo.pack(fill=tk.X)

        # Model selection (dynamic based on provider)
        model_frame = ttk.LabelFrame(main_frame, text="Model", padding="10")
        model_frame.pack(fill=tk.X, pady=(0, 10))

        self.model_combo = ttk.Combobox(model_frame, state="readonly", width=30)
        self.model_combo.pack(fill=tk.X)

        # Language selection
        lang_frame = ttk.LabelFrame(main_frame, text="Language", padding="10")
        lang_frame.pack(fill=tk.X, pady=(0, 10))

        self.language_combo = ttk.Combobox(lang_frame, state="readonly", width=50)
        self.language_combo['values'] = ("German", "English", "Auto-Detection")
        self.language_combo.current(0)
        self.language_combo.pack(fill=tk.X)

        # Hotkey configuration
        hotkey_frame = ttk.LabelFrame(main_frame, text="Hotkey Configuration", padding="10")
        hotkey_frame.pack(fill=tk.X, pady=(0, 10))

        hotkey_input_frame = ttk.Frame(hotkey_frame)
        hotkey_input_frame.pack(fill=tk.X)

        ttk.Label(hotkey_input_frame, text="Hotkey:").pack(side=tk.LEFT, padx=(0, 5))

        self.hotkey_var = tk.StringVar(value=DEFAULT_HOTKEY)
        self.hotkey_entry = ttk.Entry(hotkey_input_frame, textvariable=self.hotkey_var, width=20)
        self.hotkey_entry.pack(side=tk.LEFT, padx=(0, 5))

        self.record_hotkey_button = ttk.Button(hotkey_input_frame, text="Record", command=self.start_hotkey_recording)
        self.record_hotkey_button.pack(side=tk.LEFT)

        self.hotkey_recording = False
        self.hotkey_listener = None

        # Status display
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(status_frame, text="Ready", foreground="gray")
        self.status_label.pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(20, 0))

        self.start_button = ttk.Button(button_frame, text="Start", command=self.start, width=12)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop, state=tk.DISABLED, width=12)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.quit_button = ttk.Button(button_frame, text="Quit", command=self.on_closing, width=12)
        self.quit_button.pack(side=tk.LEFT, padx=5)

        self.about_button = ttk.Button(button_frame, text="About", command=self.show_about, width=12)
        self.about_button.pack(side=tk.LEFT, padx=5)

    def is_physical_device(self, device_name):
        """Check if device is a physical microphone (not virtual/system device)"""
        device_lower = device_name.lower()

        # Exclude only virtual/system devices that are NOT physical hardware
        exclude_exact = [
            'pipewire',
            'default',
        ]

        # Exclude devices that match these patterns exactly
        for keyword in exclude_exact:
            if device_lower == keyword:
                return False

        # Exclude devices with monitor/loopback in name
        exclude_keywords = [
            'monitor',
            'loopback',
        ]

        for keyword in exclude_keywords:
            if keyword in device_lower:
                return False

        # Include all devices with hardware identifier (hw:)
        if 'hw:' in device_lower:
            return True

        # Also include known physical device patterns
        include_indicators = [
            'usb audio',
            'røde',
            'rode',
            'videomic',
            'blue',
            'shure',
            'audio-technica',
            'samson',
            'focusrite',
            'scarlett',
            'behringer',
        ]

        for indicator in include_indicators:
            if indicator in device_lower:
                return True

        # Default: exclude unknown devices to be safe
        return False

    def get_hw_device_id(self, device_name):
        """Extract hardware device ID from ALSA device name (e.g., 'hw:3,0' from name)"""
        match = re.search(r'\(hw:(\d+),(\d+)\)', device_name)
        if match:
            card = match.group(1)
            device = match.group(2)
            return f"hw:{card},{device}"
        return None

    def populate_devices(self):
        """Populate microphone dropdown with available devices"""
        devices = sd.query_devices()
        self.device_list = []
        display_names = []
        all_input_devices = []  # Fallback: store all input devices
        default_device_info = None

        # Get the default input device
        try:
            default_device_info = sd.query_devices(kind='input')
            default_idx = default_device_info['index'] if isinstance(default_device_info, dict) else None
        except (sd.PortAudioError, OSError, KeyError):
            default_idx = None

        for idx, device in enumerate(devices):
            name = device['name']
            is_input = device['max_input_channels'] > 0

            # Only show devices with input channels
            if not is_input:
                continue

            # Store all input devices as fallback
            try:
                best_rate = self.find_best_sample_rate(idx)
            except (sd.PortAudioError, OSError):
                best_rate = 48000  # Default fallback

            all_input_devices.append((idx, name, best_rate))

            # ALWAYS include the default device, even if it's not "physical"
            if idx == default_idx:
                display_name = self.format_device_name(name, best_rate)
                self.device_list.append((idx, name, best_rate))
                display_names.append(display_name)
                continue

            # Filter to only show physical devices
            if not self.is_physical_device(name):
                continue

            # Shorten name for better readability
            display_name = self.format_device_name(name, best_rate)
            self.device_list.append((idx, name, best_rate))
            display_names.append(display_name)

        # Fallback: If no physical devices found, use all input devices
        if not self.device_list and all_input_devices:
            for idx, name, best_rate in all_input_devices:
                display_name = self.format_device_name(name, best_rate)
                self.device_list.append((idx, name, best_rate))
                display_names.append(display_name)

        # Set all values at once (more reliable than incremental updates)
        self.mic_combo['values'] = tuple(display_names)

        # Select default device
        if self.device_list:
            # Try to find and select the system default device first
            default_selected = False
            if default_idx is not None:
                for pos, (idx, name, _) in enumerate(self.device_list):
                    if idx == default_idx:
                        self.mic_combo.current(pos)
                        default_selected = True
                        break

            # If default not found and only one device, select it
            if not default_selected and len(self.device_list) == 1:
                self.mic_combo.current(0)

    def format_device_name(self, name, sample_rate):
        """Format device name for better readability"""
        # Extract meaningful part from technical names
        if ":" in name and "hw:" in name:
            # Handle ALSA names like "USB Audio: - (hw:3,0)" or "HD-Audio Generic: ALC257 Analog (hw:1,0)"
            parts = name.split(":")
            if len(parts) >= 2:
                main_name = parts[0].strip()

                # Check if there's a descriptive second part (not just "-")
                second_part = parts[1].strip()
                if second_part and second_part != "-":
                    # Extract the part before (hw:...)
                    if "(" in second_part:
                        second_part = second_part.split("(")[0].strip()
                    if second_part:
                        return f"{main_name}: {second_part} ({sample_rate}Hz)"

                # Just use the main name if second part is empty or "-"
                return f"{main_name} ({sample_rate}Hz)"

        # Special handling for common names
        if name == "default":
            return f"Default Microphone ({sample_rate}Hz)"
        elif name == "pipewire":
            return f"PipeWire ({sample_rate}Hz)"
        elif "VideoMic" in name or "RØDE" in name:
            # Extract brand/model names
            return f"{name.split(':')[0]} ({sample_rate}Hz)"

        # For long names, try to shorten
        if len(name) > 40:
            return f"{name[:37]}... ({sample_rate}Hz)"

        return f"{name} ({sample_rate}Hz)"

    def find_best_sample_rate(self, device_id):
        """Find best supported sample rate for device"""
        # Try common sample rates in order of preference
        for rate in COMMON_SAMPLE_RATES:
            try:
                sd.check_input_settings(device=device_id, samplerate=rate)
                return rate
            except (sd.PortAudioError, OSError, ValueError):
                continue
        # Fallback
        return 44100

    def load_config(self):
        """Load configuration from file"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: config.json is corrupted, resetting to defaults: {e}")
            except (IOError, OSError) as e:
                print(f"Warning: Could not read config: {e}")
        return {}

    def save_config(self):
        """Save configuration to file"""
        try:
            # Create config directory if it doesn't exist
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except (IOError, OSError) as e:
            print(f"Error saving config: {e}")

    def load_settings(self):
        """Load saved settings into GUI"""
        if 'device_name' in self.config:
            saved_name = self.config['device_name']
            # Try to find and select the saved device
            found = False
            for pos, (idx, name, _) in enumerate(self.device_list):
                # Compare actual device names (not formatted display names)
                if name == saved_name:
                    self.mic_combo.current(pos)
                    found = True
                    break

            # If not found, try partial match for legacy configs with hardware IDs
            if not found:
                for pos, (idx, name, _) in enumerate(self.device_list):
                    if ':' in name and ':' in saved_name:
                        if name.split(':')[0].strip() == saved_name.split(':')[0].strip():
                            self.mic_combo.current(pos)
                            break

        if 'language' in self.config:
            # Map language code to combobox display text using module constant
            lang_code = self.config['language']
            if lang_code in LANGUAGE_CODE_TO_INDEX:
                self.language_combo.current(LANGUAGE_CODE_TO_INDEX[lang_code])

        if 'hotkey' in self.config:
            self.hotkey_var.set(self.config['hotkey'])

        # Load provider settings (new combined format)
        if 'provider' in self.config:
            provider_config = self.config['provider']
            selected_provider = provider_config.get('selected', 'whisper-local-cpu')

            # Legacy support
            if selected_provider == 'whisper':
                # Check for legacy config with separate device setting
                if 'whisper_device' in self.config:
                    device = self.config['whisper_device']
                    selected_provider = 'whisper-local-gpu' if device == 'cuda' else 'whisper-local-cpu'
                else:
                    selected_provider = 'whisper-local-cpu'
            elif selected_provider == 'deepgram':
                selected_provider = 'deepgram-cloud'

            # Find matching display name and select it
            for display_name, internal_name in self.provider_display_to_name.items():
                if internal_name == selected_provider:
                    # Find index of this display name in combobox
                    values = self.provider_combo['values']
                    for idx, val in enumerate(values):
                        if val == display_name:
                            self.provider_combo.current(idx)
                            break
                    break

        # Populate models for selected provider
        self.populate_models()

    def on_provider_changed(self):
        """Handle provider selection change"""
        self.populate_models()

    def populate_models(self):
        """Populate model dropdown based on selected provider"""
        # Get selected provider display name and map to internal name
        selected_display = self.provider_combo.get()
        if not selected_display or selected_display not in self.provider_display_to_name:
            self.model_combo['values'] = []
            return

        provider_name = self.provider_display_to_name[selected_display]

        # Get base provider type for config lookup (whisper or deepgram)
        base_provider = 'whisper' if 'whisper' in provider_name else 'deepgram'

        try:
            from providers import create_provider
            # Create temporary instance to get available models
            provider = create_provider(provider_name)
            models = provider.get_available_models()
            self.model_combo['values'] = models

            # Select model from saved config
            saved_model = self.config.get('provider', {}).get(base_provider, {}).get('model')

            # Priority: saved config > first in list
            if saved_model and saved_model in models:
                self.model_combo.set(saved_model)
            elif models:
                self.model_combo.current(0)

            # Also restore language selection when changing providers
            if 'language' in self.config:
                lang_code = self.config['language']
                if lang_code in LANGUAGE_CODE_TO_INDEX:
                    self.language_combo.current(LANGUAGE_CODE_TO_INDEX[lang_code])
        except Exception as e:
            self.model_combo['values'] = []
            print(f"Error loading models for {provider_name}: {e}")


    def update_status(self, message):
        """Update status label (thread-safe)"""
        def _update():
            try:
                if self.status_label.winfo_exists():
                    self.status_label.config(text=message)
            except tk.TclError:
                # Widget was destroyed, ignore
                pass

        try:
            self.root.after(0, _update)
        except tk.TclError:
            # Root window was destroyed, ignore
            pass


    def start_hotkey_recording(self):
        """Start recording a new hotkey"""
        if self.is_active:
            messagebox.showwarning("Warning", "Please stop VoiceSnip before changing the hotkey.")
            return

        if self.hotkey_recording:
            return

        self.hotkey_recording = True
        self.recorded_keys = set()
        self.record_hotkey_button.config(text="Recording...", state=tk.DISABLED)
        self.hotkey_entry.config(state=tk.DISABLED)

        # Start temporary listener for hotkey recording
        self.hotkey_listener = keyboard.Listener(
            on_press=self.on_hotkey_record_press,
            on_release=self.on_hotkey_record_release
        )
        self.hotkey_listener.start()

    def on_hotkey_record_press(self, key):
        """Record key presses during hotkey recording"""
        if not self.hotkey_recording:
            return

        self.recorded_keys.add(key)

    def on_hotkey_record_release(self, key):
        """Stop recording when all keys are released"""
        if not self.hotkey_recording:
            return

        # If we have recorded keys, finalize the hotkey
        if self.recorded_keys:
            hotkey_string = self.format_hotkey(self.recorded_keys)
            self.hotkey_var.set(hotkey_string)
            self.stop_hotkey_recording()

    def format_hotkey(self, keys):
        """Format a set of keys into a hotkey string"""
        # Map pynput keys to readable names using module-level constant
        key_names = []
        modifiers = []

        for key in keys:
            if key in KEY_NAME_MAP:
                name = KEY_NAME_MAP[key]
                if name in ['ctrl', 'alt', 'shift', 'cmd']:
                    if name not in modifiers:
                        modifiers.append(name)
                else:
                    key_names.append(name)
            elif hasattr(key, 'char') and key.char:
                key_names.append(key.char.lower())

        # Sort modifiers consistently
        modifier_order = ['ctrl', 'alt', 'shift', 'cmd']
        modifiers.sort(key=lambda x: modifier_order.index(x) if x in modifier_order else 999)

        # Combine modifiers and key
        all_parts = modifiers + key_names
        return '+'.join(all_parts) if all_parts else DEFAULT_HOTKEY

    def stop_hotkey_recording(self):
        """Stop hotkey recording"""
        self.hotkey_recording = False
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

        self.record_hotkey_button.config(text="Record", state=tk.NORMAL)
        self.hotkey_entry.config(state=tk.NORMAL)
        self.recorded_keys = set()

    def start(self):
        """Start VoiceSnip"""
        # Get selected device
        selected_idx = self.mic_combo.current()
        if selected_idx < 0:
            messagebox.showerror("Error", "Please select a microphone.")
            return

        device_id, device_name, sample_rate = self.device_list[selected_idx]

        # Map language combobox to language code using module constant
        lang_idx = self.language_combo.current()
        language = LANGUAGE_INDEX_TO_CODE.get(lang_idx, 'de')

        hotkey = self.hotkey_var.get()

        # Map provider combobox to provider name (new combined format)
        selected_display = self.provider_combo.get()
        if not selected_display or selected_display not in self.provider_display_to_name:
            messagebox.showerror("Error", "Please select a valid provider.")
            return
        provider_name = self.provider_display_to_name[selected_display]

        # Get base provider type for config storage (whisper or deepgram)
        base_provider = 'whisper' if 'whisper' in provider_name else 'deepgram'

        model = self.model_combo.get()

        # Validate inputs
        if not hotkey or hotkey.strip() == "":
            messagebox.showerror("Error", "Please configure a hotkey.")
            return
        if not model:
            messagebox.showerror("Error", "Please select a model.")
            return


        # Prepare provider config
        provider_config = {'model': model}
        if provider_name == 'deepgram-cloud':
            provider_config['api_key'] = os.getenv('DEEPGRAM_API_KEY')
            provider_config['endpoint'] = os.getenv('DEEPGRAM_ENDPOINT')

        # Save settings
        if 'provider' not in self.config:
            self.config['provider'] = {}
        self.config['provider']['selected'] = provider_name
        if base_provider not in self.config['provider']:
            self.config['provider'][base_provider] = {}
        self.config['provider'][base_provider]['model'] = model

        self.config['device_name'] = device_name
        self.config['language'] = language
        self.config['hotkey'] = hotkey
        self.save_config()

        # Initialize core with provider
        try:
            self.update_status(f"Initializing {provider_name} provider...")
            self.root.update()  # Force GUI update

            self.core = VoiceSnipCore(
                device_id=device_id,
                language=language,
                sample_rate=sample_rate,
                hotkey=hotkey,
                provider_name=provider_name,
                provider_config=provider_config
            )
            self.core.set_status_callback(self.update_status)

            # Check if model needs to be downloaded (for Whisper provider)
            if 'whisper' in provider_name:
                if not self.core.stt_provider.is_model_downloaded():
                    # Show info dialog about model download
                    self.show_model_download_info(model)

            self.update_status("Ready")
            self.root.update()
        except ValueError as e:
            messagebox.showerror("Provider Error", str(e))
            self.update_status("❌ Failed to initialize")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {e}")
            self.update_status("❌ Failed to initialize")
            return

        # Start keyboard listener (non-blocking, daemon thread)
        try:
            self.listener = keyboard.Listener(
                on_press=self.core.on_press,
                on_release=self.core.on_release
            )
            self.listener.daemon = True
            self.listener.start()
        except Exception as e:
            # Cleanup on failure
            if self.listener:
                try:
                    self.listener.stop()
                except Exception:
                    pass
                self.listener = None
            messagebox.showerror("Error", f"Failed to start keyboard listener: {e}")
            self.update_status("❌ Failed to start")
            return

        # Update UI - check widgets still exist
        try:
            self.is_active = True
            if self.start_button.winfo_exists():
                self.start_button.config(state=tk.DISABLED)
            if self.stop_button.winfo_exists():
                self.stop_button.config(state=tk.NORMAL)
            if self.mic_combo.winfo_exists():
                self.mic_combo.config(state=tk.DISABLED)
            if self.provider_combo.winfo_exists():
                self.provider_combo.config(state=tk.DISABLED)
            if self.model_combo.winfo_exists():
                self.model_combo.config(state=tk.DISABLED)
            if self.hotkey_entry.winfo_exists():
                self.hotkey_entry.config(state=tk.DISABLED)
            if self.record_hotkey_button.winfo_exists():
                self.record_hotkey_button.config(state=tk.DISABLED)
            if self.language_combo.winfo_exists():
                self.language_combo.config(state=tk.DISABLED)
            self.update_status("✅ Active - Waiting for hotkey...")
        except tk.TclError as e:
            # Widget was destroyed during initialization
            print(f"Warning: GUI widget error during startup: {e}")
            if self.listener:
                self.listener.stop()
            self.is_active = False

    def stop(self):
        """Stop VoiceSnip"""
        if self.listener:
            self.listener.stop()
            self.listener = None

        # Clean up core resources (streams, threads)
        if self.core:
            self.core.cleanup()

            # Unload model to free VRAM/memory
            if self.core.stt_provider:
                self.core.stt_provider.unload_model()

        self.core = None

        # Update UI - check widgets still exist
        try:
            self.is_active = False
            if self.start_button.winfo_exists():
                self.start_button.config(state=tk.NORMAL)
            if self.stop_button.winfo_exists():
                self.stop_button.config(state=tk.DISABLED)
            if self.mic_combo.winfo_exists():
                self.mic_combo.config(state="readonly")
            if self.provider_combo.winfo_exists():
                self.provider_combo.config(state="readonly")
            if self.model_combo.winfo_exists():
                self.model_combo.config(state="readonly")
            if self.hotkey_entry.winfo_exists():
                self.hotkey_entry.config(state=tk.NORMAL)
            if self.record_hotkey_button.winfo_exists():
                self.record_hotkey_button.config(state=tk.NORMAL)
            if self.language_combo.winfo_exists():
                self.language_combo.config(state="readonly")
            self.update_status("Ready")
        except tk.TclError:
            # Widget was destroyed, ignore
            pass

    def on_closing(self):
        """Handle window close event"""
        if self.is_active:
            self.stop()
        self.root.destroy()

    def show_about(self):
        """Show About dialog with copyright, license, and GitHub info"""
        # Create About dialog window
        about_window = tk.Toplevel(self.root)
        about_window.title("About VoiceSnip")

        # Center the window
        about_window.transient(self.root)
        about_window.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(about_window, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # App title
        title_label = ttk.Label(
            main_frame,
            text="VoiceSnip",
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=(0, 5))

        # Subtitle
        subtitle_label = ttk.Label(
            main_frame,
            text="Push-to-Talk Speech-to-Text",
            font=("Arial", 10)
        )
        subtitle_label.pack(pady=(0, 20))

        # Version info
        def get_version():
            """Get version from git"""
            try:
                result = subprocess.run(
                    ['git', 'describe', '--tags', '--always'],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=2
                )
                git_output = result.stdout.strip()

                # Check if output is a tag (starts with 'v' or contains '-g')
                # Tags: v1.0.0 or v1.0.0-5-g02c8a48 (tag with commits ahead)
                # Commit-only: 02c8a48
                if git_output.startswith('v') or '-g' in git_output:
                    # It's a tag or tag with commits
                    return git_output
                else:
                    # It's just a commit hash (no tags)
                    return f"dev-{git_output}"
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return "dev"

        version_label = ttk.Label(
            main_frame,
            text=f"Version: {get_version()}",
            font=("Arial", 9)
        )
        version_label.pack(pady=(0, 20))

        # Copyright
        copyright_label = ttk.Label(
            main_frame,
            text="Copyright (c) 2025\nStefan Schmidbauer",
            font=("Arial", 10),
            justify=tk.CENTER
        )
        copyright_label.pack(pady=(0, 15))

        # License
        license_label = ttk.Label(
            main_frame,
            text="License: MIT License",
            font=("Arial", 9)
        )
        license_label.pack(pady=(0, 20))

        # GitHub link button
        def open_github():
            webbrowser.open(GITHUB_URL)

        github_button = ttk.Button(
            main_frame,
            text="GitHub Repository",
            command=open_github
        )
        github_button.pack(pady=(0, 20))

        # Separator
        separator = ttk.Separator(main_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(0, 20))

        # OpenAI Whisper attribution
        whisper_label = ttk.Label(
            main_frame,
            text="Using OpenAI Whisper\n(MIT License, Copyright (c) 2022 OpenAI)",
            font=("Arial", 8),
            justify=tk.CENTER,
            foreground="gray"
        )
        whisper_label.pack(pady=(0, 10))

        # AI development note
        ai_label = ttk.Label(
            main_frame,
            text="Developed with AI assistance\n(Claude/Anthropic)",
            font=("Arial", 8),
            justify=tk.CENTER,
            foreground="gray"
        )
        ai_label.pack(pady=(0, 20))

        # Close button
        close_button = ttk.Button(
            main_frame,
            text="Close",
            command=about_window.destroy,
            width=15
        )
        close_button.pack(pady=(10, 0))

        # Update window to calculate required size
        about_window.update_idletasks()

        # Calculate width with DPI scaling
        base_width = 450
        scaled_width = int(base_width * max(1.0, self.root.winfo_fpixels('1i') / 96.0))

        # Set minimum width and let height adjust automatically
        about_window.minsize(scaled_width, 1)
        about_window.resizable(False, False)

    def show_model_download_info(self, model):
        """Show info dialog about model download with better formatting"""
        # Create info dialog window
        info_window = tk.Toplevel(self.root)
        info_window.title("Model Download Required")

        # Center the window
        info_window.transient(self.root)
        info_window.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(info_window, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Model Download Required",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=(0, 15))

        # Info text with better line wrapping
        info_text = (
            f"The Whisper model '{model}' needs to be downloaded on first use.\n\n"
            "This will happen automatically when you press the hotkey for the first time.\n\n"
            "Larger models can take a long time to download. Please be patient.\n\n"
            "You will see 'Processing...' while the model is being downloaded and loaded."
        )

        # Calculate width with DPI scaling
        base_width = 480
        scaled_width = int(base_width * max(1.0, self.root.winfo_fpixels('1i') / 96.0))

        info_label = ttk.Label(
            main_frame,
            text=info_text,
            font=("Arial", 10),
            justify=tk.LEFT,
            wraplength=scaled_width - 50  # Leave margin for padding
        )
        info_label.pack(pady=(0, 20))

        # OK button
        ok_button = ttk.Button(
            main_frame,
            text="OK",
            command=info_window.destroy,
            width=15
        )
        ok_button.pack()

        # Set focus to OK button for easy dismissal with Enter
        ok_button.focus()

        # Update window to calculate required size
        info_window.update_idletasks()

        # Set minimum width and let height adjust automatically
        info_window.minsize(scaled_width, 1)
        info_window.resizable(False, False)


def load_installation_config():
    """Load and validate installation config.

    Returns:
        Dict with config data or None if missing
    """
    config_file = Path.home() / '.config' / 'voicesnip' / 'installation_profile.ini'

    if not config_file.exists():
        return None

    try:
        config = ConfigParser()
        config.read(config_file)

        # Validate required fields
        if 'installation' not in config:
            raise ValueError("Missing [installation] section")

        profile = config['installation'].get('profile')
        features = config['installation'].get('features', '').split(',')

        if not profile or not features:
            raise ValueError("Invalid config: missing profile or features")

        return {
            'profile': profile,
            'features': features,
            'install_date': config['installation'].get('install_date', 'unknown'),
        }

    except Exception as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Configuration Error",
            f"Invalid installation config: {e}\n\n"
            "Please run the installer to fix:\n"
            "  ./install.py --force"
        )
        root.destroy()
        return None


def main():
    """Main entry point"""
    # Load installation config
    config = load_installation_config()

    if config is None:
        # Show error dialog
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Installation Required",
            "VoiceSnip is not installed.\n\n"
            "Please run the installer first:\n"
            "  ./install.py\n\n"
            "This will configure VoiceSnip for your system."
        )
        sys.exit(1)

    # Start GUI with installation config
    root = tk.Tk()
    app = VoiceSnipGUI(root, installation_config=config)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
