"""
VoiceSnip Constants

All application-wide constants including audio configuration
and keyboard mappings.
"""

import sys
import os
from pathlib import Path
from pynput import keyboard


def get_platform_config_dir():
    """Get project directory for configuration files.

    Config files are stored in the project directory for portability.
    For PyInstaller builds, this is the directory containing the executable.
    For AppImage builds, this is the directory containing the AppImage file.
    For normal Python execution, this is the project root directory.
    """
    if getattr(sys, 'frozen', False):
        # Check if running as AppImage (Linux)
        appimage_path = os.environ.get('APPIMAGE')
        if appimage_path:
            # AppImage: use directory containing the .AppImage file
            return Path(appimage_path).parent
        else:
            # Regular PyInstaller: use directory of the executable
            return Path(sys.executable).parent
    else:
        # Normal Python: use project root (parent of voicesnip package)
        return Path(__file__).parent.parent

# Audio Configuration
TARGET_SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Common sample rates to try (in order of preference)
COMMON_SAMPLE_RATES = [16000, 44100, 48000, 22050, 8000]

# Application name (used for config filenames)
APP_NAME = "voicesnip"

# Configuration paths (in project directory for portability)
CONFIG_DIR = get_platform_config_dir()
CONFIG_FILE = CONFIG_DIR / f'{APP_NAME}_config.json'
PROFILE_FILE = CONFIG_DIR / f'{APP_NAME}_profile.ini'

# GitHub URL
GITHUB_URL = "https://github.com/Stefan-Schmidbauer/voicesnip"

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
# Only languages well-supported by both Whisper (all models) and Deepgram
# Alphabetically sorted by English name, Auto-Detection at the end
LANGUAGES = [
    ('Dutch', 'nl'),
    ('English', 'en'),
    ('French', 'fr'),
    ('German', 'de'),
    ('Italian', 'it'),
    ('Japanese', 'ja'),
    ('Korean', 'ko'),
    ('Portuguese', 'pt'),
    ('Russian', 'ru'),
    ('Spanish', 'es'),
    ('Auto-Detection', ''),
]

LANGUAGE_NAMES = [lang[0] for lang in LANGUAGES]
LANGUAGE_CODE_TO_INDEX = {lang[1]: idx for idx, lang in enumerate(LANGUAGES)}
LANGUAGE_INDEX_TO_CODE = {idx: lang[1] for idx, lang in enumerate(LANGUAGES)}

# Default hotkey
DEFAULT_HOTKEY = "ctrl+space"


def is_wayland():
    """Check if running under Wayland display server.

    Returns True if XDG_SESSION_TYPE is 'wayland', False otherwise.
    This is used to adjust behavior for Wayland limitations
    (global hotkeys don't work under Wayland).
    """
    if sys.platform == 'win32':
        return False
    return os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland'
