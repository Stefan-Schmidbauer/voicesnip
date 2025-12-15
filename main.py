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

Copyright (c) 2025 Stefan Schmidbauer
License: MIT License
GitHub: https://github.com/Stefan-Schmidbauer/voicesnip
"""

import sys
import tkinter as tk
from tkinter import messagebox

from dotenv import load_dotenv

from voicesnip.gui.config_manager import load_installation_config
from voicesnip.gui.main_window import VoiceSnipGUI

# Load environment variables
load_dotenv()


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
