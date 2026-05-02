"""
Text Insertion

Handles inserting transcribed text into active applications.
Uses xdotool on Linux X11 for reliable text insertion without clipboard.
"""

import re
import subprocess
import time

CHAR_DELAY_MS = 12
SPACE_PAUSE_S = 0.04


def insert_text(text):
    """Insert text into active application without using clipboard.

    Types non-space chunks with xdotool's normal delay, then sends each
    space as a separate keystroke with a short pause around it. Some
    terminals (e.g. gnome-terminal) drop spaces when xdotool types too
    fast; isolating spaces avoids that.

    Args:
        text: Text to insert

    Raises:
        FileNotFoundError: If xdotool is not installed
    """
    try:
        tokens = re.split(r'( +)', text)
        for token in tokens:
            if not token:
                continue
            if token[0] == ' ':
                for _ in token:
                    time.sleep(SPACE_PAUSE_S)
                    subprocess.run(
                        ['xdotool', 'key', '--clearmodifiers', 'space'],
                        check=True,
                        timeout=2.0,
                    )
                    time.sleep(SPACE_PAUSE_S)
            else:
                subprocess.run(
                    ['xdotool', 'type', '--clearmodifiers',
                     '--delay', str(CHAR_DELAY_MS), '--', token],
                    check=True,
                    timeout=15.0,
                )
    except subprocess.TimeoutExpired:
        print("Error: Text insertion timed out")
    except subprocess.CalledProcessError as e:
        print(f"Error inserting text: {e}")
    except FileNotFoundError:
        print("xdotool not found. Please install: sudo apt install xdotool")
    except Exception as e:
        print(f"Error inserting text: {e}")
