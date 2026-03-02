#!/usr/bin/env python3
"""
VoiceSnip - Push-to-Talk Speech-to-Text

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
    """Load configuration from .env or voicesnip.ini (Windows-friendly).

    Search order:
    1. .env (standard, Linux default)
    2. voicesnip.ini (Windows-friendly alternative)

    Returns the path of the loaded config file, or None if not found.
    """
    # Get the directory where the executable/script is located
    if getattr(sys, 'frozen', False):
        # Check if running as AppImage (Linux)
        appimage_path = os.environ.get('APPIMAGE')
        if appimage_path:
            # AppImage: use directory containing the .AppImage file
            base_dir = os.path.dirname(appimage_path)
        else:
            # Regular PyInstaller: use directory of the executable
            base_dir = os.path.dirname(sys.executable)
    else:
        # Running as script
        base_dir = os.path.dirname(os.path.abspath(__file__))

    config_files = ['.env', 'voicesnip.ini']

    for config_file in config_files:
        config_path = os.path.join(base_dir, config_file)
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
