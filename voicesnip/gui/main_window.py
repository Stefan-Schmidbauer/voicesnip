"""
VoiceSnip Main GUI Window

Main application window with device selection, provider configuration,
and control buttons.
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from PIL import Image, ImageTk
from pynput import keyboard

from ..constants import (
    DEFAULT_HOTKEY,
    LANGUAGE_CODE_TO_INDEX,
    LANGUAGE_INDEX_TO_CODE,
)
from ..core import VoiceSnipCore
from ..hotkey_manager import format_hotkey
from .config_manager import load_config, save_config
from .device_manager import populate_devices
from .dialogs import show_about_dialog, show_model_download_info


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller builds."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)


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
        self.config = load_config()

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
            dpi = self.root.winfo_fpixels('1i')
            scaling_factor = dpi / 96.0
            scaling_factor = max(1.0, scaling_factor)

            scaled_width = int(base_width * scaling_factor)
            scaled_height = int(base_height * scaling_factor)

            return scaled_width, scaled_height
        except Exception as e:
            print(f"Could not detect DPI scaling: {e}")
            return base_width, base_height

    def apply_window_size(self):
        """Apply window size from config or use default"""
        if 'window_width' in self.config and 'window_height' in self.config:
            width = self.config['window_width']
            height = self.config['window_height']
        else:
            base_width, base_height = 600, 800
            width, height = self.scale_window_size(base_width, base_height)

        self.root.geometry(f"{width}x{height}")

    def on_window_configure(self, event):
        """Handle window resize/move events"""
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

            if width > 100 and height > 100:
                self.config['window_width'] = width
                self.config['window_height'] = height
                save_config(self.config)
        except tk.TclError:
            pass

    def create_widgets(self):
        """Create GUI widgets"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Logo
        logo_frame = ttk.Frame(main_frame)
        logo_frame.pack(pady=(0, 20))

        try:
            png_path = get_resource_path(os.path.join("assets", "icons", "app", "voicesnip_icon.png"))
            if os.path.exists(png_path):
                image = Image.open(png_path)
                photo = ImageTk.PhotoImage(image)

                logo_label = ttk.Label(logo_frame, image=photo)
                logo_label.image = photo
                logo_label.pack()

                image.close()
        except Exception as e:
            print(f"Could not load logo: {e}")
            title_label = ttk.Label(logo_frame, text="VoiceSnip", font=("Arial", 16, "bold"))
            title_label.pack()

        # Microphone selection
        mic_frame = ttk.LabelFrame(main_frame, text="Microphone", padding="10")
        mic_frame.pack(fill=tk.X, pady=(0, 10))

        self.mic_combo = ttk.Combobox(mic_frame, state="readonly", width=50)
        self.mic_combo.pack(fill=tk.X)

        # Provider selection
        provider_frame = ttk.LabelFrame(main_frame, text="Provider", padding="10")
        provider_frame.pack(fill=tk.X, pady=(0, 10))

        self.provider_combo = ttk.Combobox(provider_frame, state="readonly", width=50)

        # Build provider list dynamically
        self.provider_display_to_name = {}
        providers = []

        if 'whisper' in self.features:
            display_name = "Whisper Local CPU (Free)"
            providers.append(display_name)
            self.provider_display_to_name[display_name] = "whisper-local-cpu"

            if 'cuda' in self.features:
                display_name = "Whisper Local GPU (Free, CUDA)"
                providers.append(display_name)
                self.provider_display_to_name[display_name] = "whisper-local-gpu"

        if 'faster-whisper-server' in self.features:
            display_name = "Faster Whisper Server"
            providers.append(display_name)
            self.provider_display_to_name[display_name] = "faster-whisper-server"

        if 'deepgram' in self.features:
            display_name = "Deepgram Cloud (API Key required)"
            providers.append(display_name)
            self.provider_display_to_name[display_name] = "deepgram-cloud"

        self.provider_combo['values'] = tuple(providers)
        if providers:
            self.provider_combo.current(0)
        else:
            messagebox.showerror("Configuration Error",
                               "No providers available. Please reinstall VoiceSnip.")
            sys.exit(1)
        self.provider_combo.bind('<<ComboboxSelected>>', lambda e: self.on_provider_changed())
        self.provider_combo.pack(fill=tk.X)

        # Model selection
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

    def populate_devices(self):
        """Populate microphone dropdown with available devices"""
        self.device_list, display_names, default_idx = populate_devices()

        self.mic_combo['values'] = tuple(display_names)

        # Select default device
        if self.device_list:
            default_selected = False
            if default_idx is not None:
                for pos, (idx, name, _) in enumerate(self.device_list):
                    if idx == default_idx:
                        self.mic_combo.current(pos)
                        default_selected = True
                        break

            if not default_selected and len(self.device_list) == 1:
                self.mic_combo.current(0)

    def load_settings(self):
        """Load saved settings into GUI"""
        if 'device_name' in self.config:
            saved_name = self.config['device_name']
            found = False
            for pos, (idx, name, _) in enumerate(self.device_list):
                if name == saved_name:
                    self.mic_combo.current(pos)
                    found = True
                    break

            if not found:
                for pos, (idx, name, _) in enumerate(self.device_list):
                    if ':' in name and ':' in saved_name:
                        if name.split(':')[0].strip() == saved_name.split(':')[0].strip():
                            self.mic_combo.current(pos)
                            break

        if 'language' in self.config:
            lang_code = self.config['language']
            if lang_code in LANGUAGE_CODE_TO_INDEX:
                self.language_combo.current(LANGUAGE_CODE_TO_INDEX[lang_code])

        if 'hotkey' in self.config:
            self.hotkey_var.set(self.config['hotkey'])

        # Load provider settings
        if 'provider' in self.config:
            provider_config = self.config['provider']
            selected_provider = provider_config.get('selected', 'whisper-local-cpu')

            # Legacy support
            if selected_provider == 'whisper':
                if 'whisper_device' in self.config:
                    device = self.config['whisper_device']
                    selected_provider = 'whisper-local-gpu' if device == 'cuda' else 'whisper-local-cpu'
                else:
                    selected_provider = 'whisper-local-cpu'
            elif selected_provider == 'deepgram':
                selected_provider = 'deepgram-cloud'

            for display_name, internal_name in self.provider_display_to_name.items():
                if internal_name == selected_provider:
                    values = self.provider_combo['values']
                    for idx, val in enumerate(values):
                        if val == display_name:
                            self.provider_combo.current(idx)
                            break
                    break

        self.populate_models()

    def on_provider_changed(self):
        """Handle provider selection change"""
        self.populate_models()

    def populate_models(self):
        """Populate model dropdown based on selected provider"""
        selected_display = self.provider_combo.get()
        if not selected_display or selected_display not in self.provider_display_to_name:
            self.model_combo['values'] = []
            return

        provider_name = self.provider_display_to_name[selected_display]
        # Determine base provider for config storage
        if 'whisper' in provider_name and 'server' not in provider_name:
            base_provider = 'whisper'
        elif 'faster-whisper-server' in provider_name:
            base_provider = 'faster-whisper-server'
        else:
            base_provider = 'deepgram'

        try:
            from providers import create_provider
            provider = create_provider(provider_name)
            models = provider.get_available_models()
            self.model_combo['values'] = models

            # Disable model dropdown if no models available (e.g. for server-based providers)
            if not models:
                self.model_combo.set("N/A (configured externally)")
                self.model_combo.config(state='disabled')
            else:
                self.model_combo.config(state='readonly')
                saved_model = self.config.get('provider', {}).get(base_provider, {}).get('model')

                if saved_model and saved_model in models:
                    self.model_combo.set(saved_model)
                elif models:
                    self.model_combo.current(0)

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
                pass

        try:
            self.root.after(0, _update)
        except tk.TclError:
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

        if self.recorded_keys:
            hotkey_string = format_hotkey(self.recorded_keys)
            self.hotkey_var.set(hotkey_string)
            self.stop_hotkey_recording()

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
        selected_idx = self.mic_combo.current()
        if selected_idx < 0:
            messagebox.showerror("Error", "Please select a microphone.")
            return

        device_id, device_name, sample_rate = self.device_list[selected_idx]

        lang_idx = self.language_combo.current()
        language = LANGUAGE_INDEX_TO_CODE.get(lang_idx, 'de')

        hotkey = self.hotkey_var.get()

        selected_display = self.provider_combo.get()
        if not selected_display or selected_display not in self.provider_display_to_name:
            messagebox.showerror("Error", "Please select a valid provider.")
            return
        provider_name = self.provider_display_to_name[selected_display]

        # Determine base provider for config storage
        if 'whisper' in provider_name and 'server' not in provider_name:
            base_provider = 'whisper'
        elif 'faster-whisper-server' in provider_name:
            base_provider = 'faster-whisper-server'
        else:
            base_provider = 'deepgram'

        model = self.model_combo.get()

        if not hotkey or hotkey.strip() == "":
            messagebox.showerror("Error", "Please configure a hotkey.")
            return

        # Only validate model if provider requires one (not for providers with external model config)
        if provider_name != 'faster-whisper-server':
            if not model or model.startswith("N/A"):
                messagebox.showerror("Error", "Please select a model.")
                return

        # Prepare provider config
        provider_config = {}

        if provider_name == 'deepgram-cloud':
            provider_config['model'] = model
            provider_config['api_key'] = os.getenv('DEEPGRAM_API_KEY')
            provider_config['endpoint'] = os.getenv('DEEPGRAM_ENDPOINT')
        elif provider_name == 'faster-whisper-server':
            # Faster Whisper Server doesn't use model parameter (configured on server)
            provider_config['endpoint'] = os.getenv('FASTER_WHISPER_ENDPOINT')
            api_key = os.getenv('FASTER_WHISPER_API_KEY')
            if api_key:
                provider_config['api_key'] = api_key
        else:
            # Local Whisper providers
            provider_config['model'] = model

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
        save_config(self.config)

        # Initialize core
        try:
            self.update_status(f"Initializing {provider_name} provider...")
            self.root.update()

            self.core = VoiceSnipCore(
                device_id=device_id,
                language=language,
                sample_rate=sample_rate,
                hotkey=hotkey,
                provider_name=provider_name,
                provider_config=provider_config
            )
            self.core.set_status_callback(self.update_status)

            # Only show model download info for local Whisper (not for server-based providers)
            if 'whisper' in provider_name and 'server' not in provider_name:
                if not self.core.stt_provider.is_model_downloaded():
                    show_model_download_info(self.root, model)

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

        # Start keyboard listener
        try:
            self.listener = keyboard.Listener(
                on_press=self.core.on_press,
                on_release=self.core.on_release
            )
            self.listener.daemon = True
            self.listener.start()
        except Exception as e:
            if self.listener:
                try:
                    self.listener.stop()
                except Exception:
                    pass
                self.listener = None
            messagebox.showerror("Error", f"Failed to start keyboard listener: {e}")
            self.update_status("❌ Failed to start")
            return

        # Update UI
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
            print(f"Warning: GUI widget error during startup: {e}")
            if self.listener:
                self.listener.stop()
            self.is_active = False

    def stop(self):
        """Stop VoiceSnip"""
        if self.listener:
            self.listener.stop()
            self.listener = None

        if self.core:
            self.core.cleanup()

            if self.core.stt_provider:
                self.core.stt_provider.unload_model()

        self.core = None

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
            pass

    def on_closing(self):
        """Handle window close event"""
        if self.is_active:
            self.stop()
        self.root.destroy()

    def show_about(self):
        """Show About dialog"""
        show_about_dialog(self.root)
