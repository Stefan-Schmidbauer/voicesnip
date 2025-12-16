"""
Text Insertion

Handles inserting transcribed text into active applications.
"""

import subprocess


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
