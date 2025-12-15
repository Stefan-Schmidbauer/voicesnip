"""
Text Insertion

Handles inserting transcribed text into active applications.
"""

import subprocess

from .constants import TERMINAL_KEYWORDS


def insert_text(text):
    """Insert text into active application without using clipboard

    Uses xdotool to type text directly, preserving the user's clipboard.

    Args:
        text: Text to insert

    Raises:
        FileNotFoundError: If xdotool is not installed
    """
    try:
        # Use xdotool type for all applications to avoid clipboard entirely
        # This preserves the user's clipboard and middle-click selection
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
        print("xdotool not found. Please install: sudo apt install xdotool")


def is_terminal_window():
    """Detect if the active window is a terminal emulator

    Returns:
        bool: True if active window is a terminal, False otherwise
    """
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
        for keyword in TERMINAL_KEYWORDS:
            if keyword in window_name_lower or keyword in window_class_lower:
                return True

        return False

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        # If detection fails, assume not a terminal
        return False
