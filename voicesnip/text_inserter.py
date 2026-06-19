"""
Text Insertion

Handles inserting transcribed text into the active application.

The display server is detected at runtime:
  - X11:     xdotool types the text directly (no clipboard).
  - Wayland: the text is placed on the clipboard (wl-copy) and pasted with
             Ctrl+V via ydotool. Typing per keystroke is avoided on Wayland
             because ydotool maps characters to US keycodes, which corrupts
             non-US layouts (e.g. German QWERTZ) and drops non-ASCII
             characters like umlauts. Clipboard paste is layout/unicode-safe.
"""

import os
import re
import subprocess
import tempfile
import time

from .constants import is_wayland

CHAR_DELAY_MS = 12
SPACE_PAUSE_S = 0.04

# ydotool's daemon listens on this socket by default.
YDOTOOL_SOCKET = os.environ.get("YDOTOOL_SOCKET", "/tmp/.ydotool_socket")

# After Ctrl+V, wait this long before restoring the previous clipboard so the
# target application has consumed our paste first (avoids a race where it would
# otherwise paste the restored old content).
CLIPBOARD_RESTORE_DELAY_S = 0.2


def insert_text(text):
    """Insert text into the active application.

    Dispatches to the Wayland (clipboard paste) or X11 (xdotool type) path
    depending on the current session.

    Args:
        text: Text to insert
    """
    if not text:
        return
    if is_wayland():
        _insert_text_wayland(text)
    else:
        _insert_text_x11(text)


# ---------------------------------------------------------------------------
# Wayland: clipboard + ydotool Ctrl+V
# ---------------------------------------------------------------------------

def _ensure_ydotoold():
    """Make sure the ydotoold daemon is running; start it on demand if not.

    Returns:
        True if the daemon socket is available, False otherwise.
    """
    if os.path.exists(YDOTOOL_SOCKET):
        return True
    try:
        # Detach so the daemon outlives this call.
        subprocess.Popen(
            ["ydotoold"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        print("ydotoold not found. Please install: sudo apt install ydotoold")
        return False
    except Exception as e:
        print(f"Error starting ydotoold: {e}")
        return False

    # Wait briefly for the socket to appear.
    for _ in range(20):
        if os.path.exists(YDOTOOL_SOCKET):
            return True
        time.sleep(0.1)
    print("ydotoold did not create its socket in time")
    return False


def _save_clipboard():
    """Capture the current clipboard so it can be restored after pasting.

    Captures only the primary advertised MIME type (an offer can advertise
    several at once; reproducing all of them with wl-copy is not possible).
    Binary data is stored in a temp file because shell/byte handling must be
    null-safe.

    Returns:
        ("EMPTY", None)        if the clipboard was empty
        (mime_type, temp_path) with the captured bytes of the primary type
        None                   if capture failed (restore is then skipped)
    """
    try:
        result = subprocess.run(
            ["wl-paste", "--list-types"],
            capture_output=True,
            timeout=5.0,
        )
    except FileNotFoundError:
        return None
    except subprocess.SubprocessError:
        return None

    if result.returncode != 0:
        # wl-paste exits non-zero when nothing is on the clipboard.
        return ("EMPTY", None)

    types = [t for t in result.stdout.decode("utf-8", "replace").splitlines() if t]
    if not types:
        return ("EMPTY", None)
    mime = types[0]

    path = None
    try:
        fd, path = tempfile.mkstemp(prefix="voicesnip-clip-")
        with os.fdopen(fd, "wb") as f:
            subprocess.run(
                ["wl-paste", "--type", mime, "--no-newline"],
                stdout=f,
                check=True,
                timeout=5.0,
            )
        return (mime, path)
    except (OSError, subprocess.SubprocessError):
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
        return None


def _restore_clipboard(saved):
    """Put the previously captured clipboard contents back."""
    if saved is None:
        return
    mime, path = saved
    try:
        if mime == "EMPTY" or path is None:
            subprocess.run(["wl-copy", "--clear"], timeout=5.0, check=False)
            return
        with open(path, "rb") as f:
            subprocess.run(
                ["wl-copy", "--type", mime],
                stdin=f,
                timeout=5.0,
                check=False,
            )
    except (OSError, subprocess.SubprocessError):
        pass


def _cleanup_clipboard_save(saved):
    """Remove the temp file created by _save_clipboard, if any."""
    if saved is None:
        return
    _, path = saved
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass


def _insert_text_wayland(text):
    """Place text on the clipboard, paste it with Ctrl+V, then restore the
    previous clipboard contents (Wayland)."""
    saved = _save_clipboard()
    pasted = False
    try:
        try:
            subprocess.run(
                ["wl-copy"],
                input=text.encode("utf-8"),
                check=True,
                timeout=5.0,
            )
        except FileNotFoundError:
            print("wl-copy not found. Please install: sudo apt install wl-clipboard")
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"Error copying text to clipboard: {e}")
            return

        if not _ensure_ydotoold():
            # Leave our text on the clipboard so the user can paste manually;
            # do not restore the old contents in that case.
            print("Text is on the clipboard - paste manually with Ctrl+V.")
            return

        # Small settle time so the clipboard offer is ready before pasting.
        time.sleep(0.05)
        try:
            # ydotool 0.1.8 'key' uses key-name syntax (ctrl+v), not code:state.
            subprocess.run(
                ["ydotool", "key", "ctrl+v"],
                check=True,
                timeout=5.0,
            )
            pasted = True
        except FileNotFoundError:
            print("ydotool not found. Please install: sudo apt install ydotool")
        except subprocess.CalledProcessError as e:
            print(f"Error pasting text (ydotoold running? /dev/uinput access?): {e}")
        except subprocess.TimeoutExpired:
            print("Error: paste timed out (ydotoold daemon?)")
    finally:
        # Only restore once our text has actually been pasted, after a short
        # delay so the target consumes it first. If pasting failed we keep our
        # text on the clipboard for a manual paste instead.
        if pasted and saved is not None:
            time.sleep(CLIPBOARD_RESTORE_DELAY_S)
            _restore_clipboard(saved)
        _cleanup_clipboard_save(saved)


# ---------------------------------------------------------------------------
# X11: xdotool type
# ---------------------------------------------------------------------------

def _insert_text_x11(text):
    """Insert text via xdotool without using the clipboard (X11).

    Types non-space chunks with xdotool's normal delay, then sends each
    space as a separate keystroke with a short pause around it. Some
    terminals (e.g. gnome-terminal) drop spaces when xdotool types too
    fast; isolating spaces avoids that.
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
