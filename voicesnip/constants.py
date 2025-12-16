"""
VoiceSnip Constants

All application-wide constants including audio configuration
and keyboard mappings.
"""

from pathlib import Path
from pynput import keyboard

# Audio Configuration
TARGET_SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

# Common sample rates to try (in order of preference)
COMMON_SAMPLE_RATES = [16000, 44100, 48000, 22050, 8000]

# Configuration paths
CONFIG_DIR = Path.home() / '.config' / 'voicesnip'
CONFIG_FILE = CONFIG_DIR / 'config.json'

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
LANGUAGE_CODE_TO_INDEX = {'de': 0, 'en': 1, '': 2}
LANGUAGE_INDEX_TO_CODE = {0: 'de', 1: 'en', 2: ''}

# Default hotkey
DEFAULT_HOTKEY = "ctrl+space"
