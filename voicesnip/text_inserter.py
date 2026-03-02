"""
Text Insertion

Handles inserting transcribed text into active applications.
Uses xdotool on Linux X11 for reliable text insertion without clipboard.
"""

import subprocess


def insert_text(text):
    """Insert text into active application without using clipboard.

    Uses xdotool for reliable text insertion on Linux X11 systems.

    Args:
        text: Text to insert

    Raises:
        FileNotFoundError: If xdotool is not installed
    """
    try:
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
    except Exception as e:
        print(f"Error inserting text: {e}")
