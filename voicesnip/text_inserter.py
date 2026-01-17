"""
Text Insertion

Handles inserting transcribed text into active applications.
"""

import subprocess
import sys
from pynput.keyboard import Controller


def insert_text(text):
    """Insert text into active application without using clipboard

    Uses platform-specific methods:
    - Windows: pynput keyboard controller (native Windows API)
    - Linux: xdotool for better clipboard preservation

    Args:
        text: Text to insert

    Raises:
        FileNotFoundError: If xdotool is not installed (Linux only)
    """
    try:
        if sys.platform == 'win32':
            # Windows: Use pynput keyboard controller (cross-platform library)
            # This uses Windows SendInput API under the hood
            keyboard = Controller()
            keyboard.type(text)
        else:
            # Linux: Use xdotool for better clipboard/middle-click preservation
            # xdotool is more reliable on Linux X11 systems
            subprocess.run(
                ['xdotool', 'type', '--clearmodifiers', '--', text],
                check=True,
                timeout=10.0  # Longer timeout for long text
            )

    except subprocess.TimeoutExpired:
        print("Error: Text insertion timed out")
    except subprocess.CalledProcessError as e:
        print(f"Error inserting text: {e}")
    except FileNotFoundError:
        if sys.platform == 'win32':
            print("Error: pynput not available. Please reinstall VoiceSnip.")
        else:
            print("xdotool not found. Please install: sudo apt install xdotool")
    except Exception as e:
        print(f"Error inserting text: {e}")
