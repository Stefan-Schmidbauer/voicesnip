#!/usr/bin/env python3
"""
VoiceSnip - Push-to-Talk Speech-to-Text

Simple GUI for selecting microphone, language, provider, and hotkey.
Press and hold your configured hotkey (default: Ctrl+Space) to record audio.
Release to transcribe and insert text into the active application.

Speech-to-Text Providers:
- Whisper Local CPU: Local processing using Faster Whisper on the CPU (no GPU)
- Whisper Local GPU (CUDA): Local processing using Faster Whisper with NVIDIA GPU
- Whisper Local GPU (ROCm): Local processing using Whisper with AMD GPU

Features:
- Configurable hotkey (e.g., Ctrl+Space, Alt+R, Ctrl+Shift+V)
- Local-only STT with CPU, CUDA and ROCm backends
- Automatic terminal detection for better paste support
- Settings persistence

Copyright (c) Stefan Schmidbauer
License: MIT License
GitHub: https://github.com/Stefan-Schmidbauer/voicesnip
"""

import os
import sys
import customtkinter as ctk
from tkinter import messagebox

from dotenv import load_dotenv

from voicesnip.gui.config_manager import load_installation_config
from voicesnip.gui.main_window import VoiceSnipGUI


def load_config_file():
    """Load configuration from .env file.

    Returns the path of the loaded config file, or None if not found.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(base_dir, '.env')
    if os.path.exists(config_path):
        load_dotenv(config_path)
        return config_path

    # Fallback: try default load_dotenv behavior (searches parent dirs)
    load_dotenv()
    return None


# Load environment variables from config file
load_config_file()


def main():
    """Main entry point"""
    # Load installation config
    config = load_installation_config()

    if config is None:
        # Show error dialog
        root = ctk.CTk()
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
    root = ctk.CTk()
    app = VoiceSnipGUI(root, installation_config=config)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully (same as clicking Quit)
        app.on_closing()
        sys.exit(0)


if __name__ == "__main__":
    main()
