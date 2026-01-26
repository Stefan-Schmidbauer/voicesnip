"""
VoiceSnip Main GUI Window

Main application window with device selection, provider configuration,
and control buttons. Uses CustomTkinter for a modern look.
"""

import os
import sys
import glob
import platform
import customtkinter as ctk
from tkinter import messagebox
from pathlib import Path
from PIL import Image
from pynput import keyboard

from ..constants import (
    DEFAULT_HOTKEY,
    LANGUAGE_CODE_TO_INDEX,
    LANGUAGE_INDEX_TO_CODE,
    LANGUAGE_NAMES,
    is_wayland,
)
from ..core import VoiceSnipCore
from ..hotkey_manager import format_hotkey
from .config_manager import load_config, save_config
from .device_manager import populate_devices
from .dialogs import show_about_dialog, show_model_download_info

# Set appearance mode and color theme
ctk.set_appearance_mode("light")  # "dark", "light", or "system"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller builds."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)


def find_cuda_dlls():
    """
    Check if required CUDA libraries are available.
    Windows: Search for DLLs in PATH and standard NVIDIA installation paths
    Linux: Search for .so files in LD_LIBRARY_PATH and standard locations

    Returns:
        tuple: (cudnn_found, cublas_found, details_dict)
    """
    cudnn_found = False
    cublas_found = False
    cudnn_path = None
    cublas_path = None

    if platform.system() == 'Windows':
        # Windows: Search in PATH and standard NVIDIA installation directories
        search_dirs = os.environ.get('PATH', '').split(os.pathsep)

        # Add standard NVIDIA CUDA Toolkit paths (prefer CUDA 12.x)
        cuda_base = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA'
        if os.path.isdir(cuda_base):
            # Find all CUDA versions, prefer 12.x
            cuda_versions = sorted(glob.glob(os.path.join(cuda_base, 'v12.*')), reverse=True)
            cuda_versions += sorted(glob.glob(os.path.join(cuda_base, 'v*')), reverse=True)
            for cuda_dir in cuda_versions:
                bin_dir = os.path.join(cuda_dir, 'bin')
                if os.path.isdir(bin_dir) and bin_dir not in search_dirs:
                    search_dirs.append(bin_dir)
                # Also check bin/x64 subdirectory
                bin_x64_dir = os.path.join(cuda_dir, 'bin', 'x64')
                if os.path.isdir(bin_x64_dir) and bin_x64_dir not in search_dirs:
                    search_dirs.append(bin_x64_dir)

        # Add standard NVIDIA cuDNN paths (prefer 12.x)
        cudnn_base = r'C:\Program Files\NVIDIA\CUDNN'
        if os.path.isdir(cudnn_base):
            # Find all cuDNN versions
            for cudnn_version_dir in glob.glob(os.path.join(cudnn_base, 'v*')):
                # Check for CUDA 12.x subdirectories first
                cuda12_dirs = sorted(glob.glob(os.path.join(cudnn_version_dir, 'bin', '12.*', 'x64')), reverse=True)
                for bin_dir in cuda12_dirs:
                    if os.path.isdir(bin_dir) and bin_dir not in search_dirs:
                        search_dirs.append(bin_dir)
                # Also check other CUDA versions
                other_dirs = sorted(glob.glob(os.path.join(cudnn_version_dir, 'bin', '*', 'x64')), reverse=True)
                for bin_dir in other_dirs:
                    if os.path.isdir(bin_dir) and bin_dir not in search_dirs:
                        search_dirs.append(bin_dir)

        cudnn_pattern = 'cudnn64_*.dll'
        cublas_pattern = 'cublas64_*.dll'
    else:
        # Linux: Search in LD_LIBRARY_PATH and standard locations
        search_dirs = os.environ.get('LD_LIBRARY_PATH', '').split(os.pathsep)
        search_dirs.extend([
            '/usr/lib/x86_64-linux-gnu',
            '/usr/local/cuda/lib64',
            '/usr/lib64',
            '/usr/local/lib',
        ])
        cudnn_pattern = 'libcudnn.so*'
        cublas_pattern = 'libcublas.so*'

    for search_dir in search_dirs:
        if not search_dir or not os.path.isdir(search_dir):
            continue

        if not cudnn_found:
            matches = glob.glob(os.path.join(search_dir, cudnn_pattern))
            if matches:
                cudnn_found = True
                cudnn_path = matches[0]

        if not cublas_found:
            matches = glob.glob(os.path.join(search_dir, cublas_pattern))
            if matches:
                cublas_found = True
                cublas_path = matches[0]

        if cudnn_found and cublas_found:
            break

    return cudnn_found, cublas_found, {'cudnn': cudnn_path, 'cublas': cublas_path}


class VoiceSnipGUI:
    """CustomTkinter GUI for VoiceSnip"""

    def __init__(self, root, installation_config):
        self.root = root
        self.root.title("VoiceSnip")

        self.core = None
        self.listener = None
        self.is_active = False
        self.is_wayland = is_wayland()
        self.last_transcription = ""
        self.is_gui_recording = False  # For GUI-based recording (Wayland)

        # Store installation config
        self.installation_config = installation_config
        self.features = installation_config['features']

        # Load config
        self.config = load_config()

        # Apply UI scaling (only widget scaling, not window scaling to avoid cumulative effect)
        if 'ui_scaling' in self.config:
            scaling = self.config['ui_scaling']
            ctk.set_widget_scaling(scaling)

        # Set window size from config or default
        width = self.config.get('window_width', 700)
        height = self.config.get('window_height', 580)
        self.root.geometry(f"{width}x{height}")
        self.root.resizable(True, True)

        # Bind window resize event to save size (delayed to avoid saving during startup)
        self._resize_after_id = None
        self._allow_size_save = False
        self.root.bind('<Configure>', self._on_window_configure)
        # Allow size saving after window is fully initialized (2 seconds delay)
        self.root.after(2000, self._enable_size_save)

        # Create UI
        self.create_widgets()

        # Populate devices
        self.populate_devices()

        # Load saved settings
        self.load_settings()

    def _enable_size_save(self):
        """Enable saving window size after startup is complete"""
        self._allow_size_save = True

    def _on_window_configure(self, event):
        """Handle window resize/move events"""
        if event.widget != self.root:
            return

        # Don't save during startup to avoid cumulative growth
        if not self._allow_size_save:
            return

        # Debounce: only save after user stops resizing for 500ms
        if self._resize_after_id:
            self.root.after_cancel(self._resize_after_id)

        self._resize_after_id = self.root.after(500, self._save_window_size)

    def _save_window_size(self):
        """Save current window size to config"""
        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            # Compensate for UI scaling to avoid cumulative growth
            # winfo_width/height returns scaled size, but geometry() expects unscaled
            scaling = self.config.get('ui_scaling', 1.0)
            if scaling != 1.0:
                width = int(width / scaling)
                height = int(height / scaling)

            if width > 100 and height > 100:
                self.config['window_width'] = width
                self.config['window_height'] = height
                save_config(self.config)
        except Exception:
            pass

    def toggle_theme(self):
        """Toggle between light and dark mode"""
        current = ctk.get_appearance_mode()
        new_mode = "dark" if current == "Light" else "light"
        ctk.set_appearance_mode(new_mode)
        # Update button text
        self.theme_button.configure(text="Dark theme" if new_mode == "light" else "Light theme")
        # Save preference
        self.config['theme'] = new_mode
        save_config(self.config)

    def adjust_scaling(self, delta):
        """Adjust UI scaling by delta (e.g., +0.1 or -0.1)"""
        current = self.config.get('ui_scaling', 1.0)
        new_scaling = round(current + delta, 1)
        # Clamp between 0.8 and 1.8
        new_scaling = max(0.8, min(1.8, new_scaling))
        if new_scaling != current:
            self.config['ui_scaling'] = new_scaling
            save_config(self.config)
            ctk.set_widget_scaling(new_scaling)

    def create_widgets(self):
        """Create GUI widgets"""
        # Base font size for the UI
        label_font = ctk.CTkFont(size=14)
        combo_font = ctk.CTkFont(size=14)
        button_font = ctk.CTkFont(size=14)
        heading_font = ctk.CTkFont(size=16, weight="bold")

        # Main scrollable frame
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # === Settings Frame ===
        settings_frame = ctk.CTkFrame(main_frame)
        settings_frame.pack(fill="x", pady=(0, 10))

        settings_label = ctk.CTkLabel(
            settings_frame,
            text="Settings",
            font=heading_font
        )
        settings_label.pack(anchor="w", padx=15, pady=(10, 5))

        settings_inner = ctk.CTkFrame(settings_frame, fg_color="transparent")
        settings_inner.pack(fill="x", padx=15, pady=(0, 10))

        # Grid layout for settings
        settings_inner.columnconfigure(1, weight=1)

        # Microphone selection
        ctk.CTkLabel(settings_inner, text="Microphone:", width=110, anchor="w", font=label_font).grid(
            row=0, column=0, sticky="w", pady=6
        )
        self.mic_combo = ctk.CTkComboBox(settings_inner, state="readonly", width=400, font=combo_font)
        self.mic_combo.grid(row=0, column=1, sticky="ew", pady=6, padx=(10, 0))

        # Provider selection
        ctk.CTkLabel(settings_inner, text="Provider:", width=110, anchor="w", font=label_font).grid(
            row=1, column=0, sticky="w", pady=6
        )
        self.provider_combo = ctk.CTkComboBox(
            settings_inner,
            state="readonly",
            width=400,
            font=combo_font,
            command=lambda _: self.on_provider_changed()
        )

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

        self.provider_combo.configure(values=providers)
        if providers:
            self.provider_combo.set(providers[0])
        else:
            messagebox.showerror("Configuration Error",
                               "No providers available. Please reinstall VoiceSnip.")
            sys.exit(1)
        self.provider_combo.grid(row=1, column=1, sticky="ew", pady=6, padx=(10, 0))

        # Model selection
        ctk.CTkLabel(settings_inner, text="Model:", width=110, anchor="w", font=label_font).grid(
            row=2, column=0, sticky="w", pady=6
        )
        self.model_combo = ctk.CTkComboBox(settings_inner, state="readonly", width=400, font=combo_font)
        self.model_combo.grid(row=2, column=1, sticky="ew", pady=6, padx=(10, 0))

        # Language selection
        ctk.CTkLabel(settings_inner, text="Language:", width=110, anchor="w", font=label_font).grid(
            row=3, column=0, sticky="w", pady=6
        )
        self.language_combo = ctk.CTkComboBox(settings_inner, state="readonly", width=400, font=combo_font, values=LANGUAGE_NAMES)
        # Default to German
        self.language_combo.set(LANGUAGE_NAMES[LANGUAGE_CODE_TO_INDEX.get('de', 0)])
        self.language_combo.grid(row=3, column=1, sticky="ew", pady=6, padx=(10, 0))

        # Hotkey configuration
        ctk.CTkLabel(settings_inner, text="Hotkey:", width=110, anchor="w", font=label_font).grid(
            row=4, column=0, sticky="w", pady=6
        )
        hotkey_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        hotkey_frame.grid(row=4, column=1, sticky="ew", pady=6, padx=(10, 0))

        self.record_hotkey_button = ctk.CTkButton(
            hotkey_frame,
            text="Set",
            command=self.start_hotkey_recording,
            width=100,
            font=button_font,
            text_color=("gray10", "gray90"),
            text_color_disabled=("gray70", "gray60")
        )
        self.record_hotkey_button.pack(side="right")

        self.hotkey_entry = ctk.CTkEntry(hotkey_frame, font=combo_font)
        self.hotkey_entry.insert(0, DEFAULT_HOTKEY)
        self.hotkey_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.hotkey_recording = False
        self.hotkey_listener = None

        # Status display with theme toggle on the right
        ctk.CTkLabel(settings_inner, text="Status:", width=110, anchor="w", font=label_font).grid(
            row=5, column=0, sticky="w", pady=6
        )
        status_frame = ctk.CTkFrame(settings_inner, fg_color="transparent")
        status_frame.grid(row=5, column=1, sticky="ew", pady=6, padx=(10, 0))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=label_font,
            text_color=("gray50", "gray70")
        )
        self.status_label.pack(side="left")

        self.theme_button = ctk.CTkButton(
            status_frame,
            text="Dark theme",
            command=self.toggle_theme,
            width=110,
            height=28,
            font=ctk.CTkFont(size=13),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            text_color=("gray10", "gray90")
        )
        self.theme_button.pack(side="right")

        # Font size buttons
        self.font_increase_button = ctk.CTkButton(
            status_frame,
            text="A+",
            command=lambda: self.adjust_scaling(0.1),
            width=36,
            height=28,
            font=ctk.CTkFont(size=13),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            text_color=("gray10", "gray90")
        )
        self.font_increase_button.pack(side="right", padx=(0, 5))

        self.font_decrease_button = ctk.CTkButton(
            status_frame,
            text="A-",
            command=lambda: self.adjust_scaling(-0.1),
            width=36,
            height=28,
            font=ctk.CTkFont(size=13),
            fg_color=("gray75", "gray25"),
            hover_color=("gray65", "gray35"),
            text_color=("gray10", "gray90")
        )
        self.font_decrease_button.pack(side="right", padx=(0, 5))

        # === Transcription Frame ===
        transcription_frame = ctk.CTkFrame(main_frame)
        transcription_frame.pack(fill="both", expand=True, pady=(0, 10))

        transcription_label = ctk.CTkLabel(
            transcription_frame,
            text="Transcription",
            font=heading_font
        )
        transcription_label.pack(anchor="w", padx=15, pady=(10, 5))

        # Text widget
        self.transcription_text = ctk.CTkTextbox(
            transcription_frame,
            height=80,
            wrap="word",
            state="disabled",
            font=ctk.CTkFont(size=15)
        )
        self.transcription_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        # Transcription buttons frame
        transcription_buttons = ctk.CTkFrame(transcription_frame, fg_color="transparent")
        transcription_buttons.pack(fill="x", padx=15, pady=(0, 10))

        self.copy_button = ctk.CTkButton(
            transcription_buttons,
            text="Copy to Clipboard",
            command=self.copy_transcription,
            state="disabled",
            width=160,
            font=button_font,
            text_color=("gray10", "gray90"),
            text_color_disabled=("gray70", "gray60")
        )
        self.copy_button.pack(side="left", padx=(0, 10))

        # Auto-clipboard checkbox
        self.auto_clipboard_var = ctk.BooleanVar(value=False)
        self.auto_clipboard_check = ctk.CTkCheckBox(
            transcription_buttons,
            text="Auto-copy to clipboard",
            variable=self.auto_clipboard_var,
            font=label_font
        )
        self.auto_clipboard_check.pack(side="left")

        # Record button for GUI-based recording (useful for Wayland)
        self.gui_record_button = ctk.CTkButton(
            transcription_buttons,
            text="Start Recording",
            command=self.toggle_gui_recording,
            state="disabled",
            width=160,
            font=button_font,
            fg_color=("#3a7ebf", "#1f538d"),
            hover_color=("#325882", "#14375e"),
            text_color=("gray10", "gray90"),
            text_color_disabled=("gray70", "gray60")
        )
        self.gui_record_button.pack(side="right")

        # === Control Buttons Frame ===
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(10, 0))

        self.start_button = ctk.CTkButton(
            button_frame,
            text="Start",
            command=self.start,
            width=110,
            font=button_font,
            fg_color=("#2d8f2d", "#1e6b1e"),
            hover_color=("#247024", "#155215"),
            text_color=("gray10", "gray90"),
            text_color_disabled=("gray70", "gray60")
        )
        self.start_button.pack(side="left", padx=5)

        self.stop_button = ctk.CTkButton(
            button_frame,
            text="Stop",
            command=self.stop,
            state="disabled",
            width=110,
            font=button_font,
            fg_color=("#c44040", "#8b2d2d"),
            hover_color=("#9e3333", "#6b2323"),
            text_color=("gray10", "gray90"),
            text_color_disabled=("gray70", "gray60")
        )
        self.stop_button.pack(side="left", padx=5)

        self.about_button = ctk.CTkButton(
            button_frame,
            text="About",
            command=self.show_about,
            width=110,
            font=button_font
        )
        self.about_button.pack(side="left", padx=5)

        self.quit_button = ctk.CTkButton(
            button_frame,
            text="Quit",
            command=self.on_closing,
            width=110,
            font=button_font,
            fg_color=("gray60", "gray40"),
            hover_color=("gray50", "gray30")
        )
        self.quit_button.pack(side="left", padx=5)

    def populate_devices(self):
        """Populate microphone dropdown with available devices"""
        self.device_list, display_names, default_idx = populate_devices()

        self.mic_combo.configure(values=display_names)

        # Select default device
        if self.device_list:
            default_selected = False
            if default_idx is not None:
                for pos, (idx, name, _) in enumerate(self.device_list):
                    if idx == default_idx:
                        self.mic_combo.set(display_names[pos])
                        default_selected = True
                        break

            if not default_selected and len(self.device_list) == 1:
                self.mic_combo.set(display_names[0])

    def load_settings(self):
        """Load saved settings into GUI"""
        # Load theme preference
        if 'theme' in self.config:
            theme = self.config['theme']
            ctk.set_appearance_mode(theme)
            self.theme_button.configure(text="Dark theme" if theme == "light" else "Light theme")

        display_names = list(self.mic_combo.cget("values"))

        if 'device_name' in self.config:
            saved_name = self.config['device_name']
            found = False
            for pos, (idx, name, _) in enumerate(self.device_list):
                if name == saved_name:
                    self.mic_combo.set(display_names[pos])
                    found = True
                    break

            if not found:
                for pos, (idx, name, _) in enumerate(self.device_list):
                    if ':' in name and ':' in saved_name:
                        if name.split(':')[0].strip() == saved_name.split(':')[0].strip():
                            self.mic_combo.set(display_names[pos])
                            break

        if 'language' in self.config:
            lang_code = self.config['language']
            if lang_code in LANGUAGE_CODE_TO_INDEX:
                self.language_combo.set(LANGUAGE_NAMES[LANGUAGE_CODE_TO_INDEX[lang_code]])

        if 'hotkey' in self.config:
            self.hotkey_entry.delete(0, "end")
            self.hotkey_entry.insert(0, self.config['hotkey'])

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
                    self.provider_combo.set(display_name)
                    break

        # Load auto-clipboard setting
        if 'auto_clipboard' in self.config:
            self.auto_clipboard_var.set(self.config['auto_clipboard'])

        self.populate_models()

    def on_provider_changed(self):
        """Handle provider selection change"""
        self.populate_models()

    def populate_models(self):
        """Populate model dropdown based on selected provider"""
        selected_display = self.provider_combo.get()
        if not selected_display or selected_display not in self.provider_display_to_name:
            self.model_combo.configure(values=[])
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
            self.model_combo.configure(values=models)

            # Disable model dropdown if no models available (e.g. for server-based providers)
            if not models:
                self.model_combo.set("N/A (configured externally)")
                self.model_combo.configure(state='disabled')
            else:
                self.model_combo.configure(state='readonly')
                saved_model = self.config.get('provider', {}).get(base_provider, {}).get('model')

                if saved_model and saved_model in models:
                    self.model_combo.set(saved_model)
                elif models:
                    self.model_combo.set(models[0])

            if 'language' in self.config:
                lang_code = self.config['language']
                if lang_code in LANGUAGE_CODE_TO_INDEX:
                    self.language_combo.set(LANGUAGE_NAMES[LANGUAGE_CODE_TO_INDEX[lang_code]])
        except Exception as e:
            self.model_combo.configure(values=[])
            print(f"Error loading models for {provider_name}: {e}")

    def update_status(self, message):
        """Update status label (thread-safe)"""
        def _update():
            try:
                if self.status_label.winfo_exists():
                    self.status_label.configure(text=message)
            except Exception:
                pass

        try:
            self.root.after(0, _update)
        except Exception:
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
        self.record_hotkey_button.configure(text="Setting...", state="disabled")
        self.hotkey_entry.configure(state="disabled")

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
            self.hotkey_entry.configure(state="normal")
            self.hotkey_entry.delete(0, "end")
            self.hotkey_entry.insert(0, hotkey_string)
            self.stop_hotkey_recording()

    def stop_hotkey_recording(self):
        """Stop hotkey recording"""
        self.hotkey_recording = False
        if self.hotkey_listener:
            self.hotkey_listener.stop()
            self.hotkey_listener = None

        self.record_hotkey_button.configure(text="Set", state="normal")
        self.hotkey_entry.configure(state="normal")
        self.recorded_keys = set()

    def start(self):
        """Start VoiceSnip"""
        # Show Wayland info on first start
        if self.is_wayland and not self.config.get('wayland_info_shown', False):
            messagebox.showinfo(
                "Wayland Detected",
                "VoiceSnip detected that you are running Wayland.\n\n"
                "Global hotkeys do not work under Wayland due to security restrictions.\n\n"
                "Please use the 'Start Recording' button in the GUI to record audio.\n"
                "Enable 'Auto-copy to clipboard' to automatically copy transcriptions."
            )
            self.config['wayland_info_shown'] = True
            save_config(self.config)

        # Get selected mic index
        selected_display = self.mic_combo.get()
        display_names = list(self.mic_combo.cget("values"))
        if not selected_display or selected_display not in display_names:
            messagebox.showerror("Error", "Please select a microphone.")
            return
        selected_idx = display_names.index(selected_display)

        device_id, device_name, sample_rate = self.device_list[selected_idx]

        # Get language
        selected_lang = self.language_combo.get()
        lang_idx = LANGUAGE_NAMES.index(selected_lang) if selected_lang in LANGUAGE_NAMES else 0
        language = LANGUAGE_INDEX_TO_CODE.get(lang_idx, 'de')

        hotkey = self.hotkey_entry.get()

        selected_provider_display = self.provider_combo.get()
        if not selected_provider_display or selected_provider_display not in self.provider_display_to_name:
            messagebox.showerror("Error", "Please select a valid provider.")
            return
        provider_name = self.provider_display_to_name[selected_provider_display]

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
        self.config['auto_clipboard'] = self.auto_clipboard_var.get()
        save_config(self.config)

        # CUDA validation for GPU provider
        if provider_name == 'whisper-local-gpu':
            cudnn_found, cublas_found, dll_details = find_cuda_dlls()

            if not cudnn_found or not cublas_found:
                missing = []
                if platform.system() == 'Windows':
                    if not cudnn_found:
                        missing.append("cuDNN (cudnn64_*.dll)")
                    if not cublas_found:
                        missing.append("cuBLAS (cublas64_*.dll)")
                    install_hint = (
                        "To enable GPU acceleration:\n"
                        "1. Install NVIDIA CUDA Toolkit + cuDNN\n"
                        "2. Ensure CUDA bin directory is in PATH\n"
                        "   (e.g., C:\\Program Files\\NVIDIA\\CUDNN\\v9.x\\bin)"
                    )
                else:
                    if not cudnn_found:
                        missing.append("cuDNN (libcudnn.so)")
                    if not cublas_found:
                        missing.append("cuBLAS (libcublas.so)")
                    install_hint = (
                        "To enable GPU acceleration:\n"
                        "1. Install CUDA libraries via pip in a venv:\n"
                        "   pip install nvidia-cudnn-cu12 nvidia-cublas-cu12\n"
                        "2. Or install CUDA Toolkit system-wide"
                    )

                messagebox.showerror(
                    "CUDA Libraries Not Found",
                    "Missing CUDA libraries:\n"
                    + "\n".join(f"• {m}" for m in missing) + "\n\n"
                    + install_hint + "\n\n"
                    "Alternative: Select 'Whisper Local CPU' instead."
                )
                return

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
            self.core.set_text_callback(self.update_transcription)

            # Only show model download info for local Whisper (not for server-based providers)
            if 'whisper' in provider_name and 'server' not in provider_name:
                if not self.core.stt_provider.is_model_downloaded():
                    show_model_download_info(self.root, model)

            self.update_status("Ready")
            self.root.update()
        except ValueError as e:
            messagebox.showerror("Provider Error", str(e))
            self.update_status("Failed to initialize")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {e}")
            self.update_status("Failed to initialize")
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
            self.update_status("Failed to start")
            return

        # Update UI
        try:
            self.is_active = True
            if self.start_button.winfo_exists():
                self.start_button.configure(state="disabled")
            if self.stop_button.winfo_exists():
                self.stop_button.configure(state="normal")
            if self.mic_combo.winfo_exists():
                self.mic_combo.configure(state="disabled")
            if self.provider_combo.winfo_exists():
                self.provider_combo.configure(state="disabled")
            if self.model_combo.winfo_exists():
                self.model_combo.configure(state="disabled")
            if self.hotkey_entry.winfo_exists():
                self.hotkey_entry.configure(state="disabled")
            if self.record_hotkey_button.winfo_exists():
                self.record_hotkey_button.configure(state="disabled")
            if self.language_combo.winfo_exists():
                self.language_combo.configure(state="disabled")
            if self.gui_record_button.winfo_exists():
                self.gui_record_button.configure(state="normal")

            # Show appropriate status message
            if self.is_wayland:
                self.update_status("Active - Use Record button (Wayland)")
            else:
                self.update_status("Active - Waiting for hotkey...")
        except Exception as e:
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
                self.start_button.configure(state="normal")
            if self.stop_button.winfo_exists():
                self.stop_button.configure(state="disabled")
            if self.mic_combo.winfo_exists():
                self.mic_combo.configure(state="readonly")
            if self.provider_combo.winfo_exists():
                self.provider_combo.configure(state="readonly")
            if self.model_combo.winfo_exists():
                self.model_combo.configure(state="readonly")
            if self.hotkey_entry.winfo_exists():
                self.hotkey_entry.configure(state="normal")
            if self.record_hotkey_button.winfo_exists():
                self.record_hotkey_button.configure(state="normal")
            if self.language_combo.winfo_exists():
                self.language_combo.configure(state="readonly")
            if self.gui_record_button.winfo_exists():
                self.gui_record_button.configure(state="disabled", text="Start Recording")
            self.is_gui_recording = False
            self.update_status("Ready")
        except Exception:
            pass

    def on_closing(self):
        """Handle window close event"""
        if self.is_active:
            self.stop()
        self.root.destroy()

    def show_about(self):
        """Show About dialog"""
        show_about_dialog(self.root)

    def update_transcription(self, text):
        """Update transcription text field (thread-safe)"""
        def _update():
            try:
                if self.transcription_text.winfo_exists():
                    self.transcription_text.configure(state="normal")
                    self.transcription_text.delete("1.0", "end")
                    self.transcription_text.insert("end", text)
                    self.transcription_text.configure(state="disabled")
                    self.last_transcription = text

                    # Enable copy button
                    if self.copy_button.winfo_exists():
                        self.copy_button.configure(state="normal")

                    # Auto-copy to clipboard if enabled
                    if self.auto_clipboard_var.get():
                        self.copy_to_clipboard(text)
            except Exception:
                pass

        try:
            self.root.after(0, _update)
        except Exception:
            pass

    def copy_transcription(self):
        """Copy last transcription to clipboard"""
        if self.last_transcription:
            self.copy_to_clipboard(self.last_transcription)
            self.update_status("Copied to clipboard")

    def copy_to_clipboard(self, text):
        """Copy text to system clipboard"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()  # Process clipboard without triggering after() callbacks
        except Exception:
            pass

    def toggle_gui_recording(self):
        """Toggle recording via GUI button (for Wayland support)"""
        if not self.core:
            return

        if self.is_gui_recording:
            # Stop recording
            self.is_gui_recording = False
            self.gui_record_button.configure(text="Start Recording")
            self.core.stop_recording()
        else:
            # Start recording
            self.is_gui_recording = True
            self.gui_record_button.configure(text="Stop Recording")
            self.core.start_recording()
