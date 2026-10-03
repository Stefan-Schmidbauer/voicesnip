"""
Text Insertion

Handles inserting transcribed text into the active application.

The display server is detected at runtime:
  - X11:     xdotool types the text directly (no clipboard).
  - Wayland: the text is placed on the clipboard (wl-copy) and pasted with
             Ctrl+V via ydotool. Typing per keystroke is avoided on Wayland
             because ydotool maps characters to US keycodes, which corrupts
             non-US layouts (e.g. German QWERTZ, Czech QWERTZ) and drops
             non-ASCII characters like umlauts or caron/acute letters.
             Clipboard paste is layout/unicode-safe.

Environment overrides (Wayland path):
  YDOTOOL_SOCKET            explicit path to the ydotoold socket
  VOICESNIP_PASTE_SHORTCUT  shortcut used to paste (default "ctrl+v"; use
                            "ctrl+shift+v" for terminal emulators)
"""

import os
import re
import subprocess
import tempfile
import time

from .constants import is_wayland

CHAR_DELAY_MS = 12
SPACE_PAUSE_S = 0.04

# Where ydotoold puts its socket depends on the version: 1.0 and newer use
# $XDG_RUNTIME_DIR/.ydotool_socket, 0.1.x used /tmp/.ydotool_socket. Probe both
# so a self-compiled daemon is found as well as the Debian/Ubuntu package.
YDOTOOL_SOCKET_ENV = os.environ.get("YDOTOOL_SOCKET")

# Shortcut used to paste. Terminal emulators need ctrl+shift+v instead.
PASTE_SHORTCUT = os.environ.get("VOICESNIP_PASTE_SHORTCUT", "ctrl+v").strip().lower()

# Raw evdev keycodes from linux/input-event-codes.h. ydotool >= 1.0 dropped the
# key-name syntax ("ctrl+v") and only accepts "<keycode>:<pressed>" pairs.
_MODIFIER_KEYCODES = {
    "ctrl": 29, "control": 29,
    "shift": 42,
    "alt": 56,
    "super": 125, "meta": 125, "win": 125,
}
_KEYCODES = {"v": 47, "insert": 110}

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

def _socket_candidates():
    """Paths where a running ydotoold may have put its socket."""
    if YDOTOOL_SOCKET_ENV:
        return [YDOTOOL_SOCKET_ENV]
    paths = []
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir:
        paths.append(os.path.join(runtime_dir, ".ydotool_socket"))  # ydotool >= 1.0
    paths.append("/tmp/.ydotool_socket")                            # ydotool 0.1.x
    return paths


def _find_ydotool_socket():
    """Return the first existing ydotoold socket, or None."""
    for path in _socket_candidates():
        if os.path.exists(path):
            return path
    return None


def _ensure_ydotoold():
    """Make sure the ydotoold daemon is running; start it on demand if not.

    Returns:
        The path of the daemon socket, or None if it never appeared.
    """
    socket_path = _find_ydotool_socket()
    if socket_path:
        return socket_path
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
        return None
    except Exception as e:
        print(f"Error starting ydotoold: {e}")
        return None

    # Wait briefly for the socket to appear.
    for _ in range(20):
        socket_path = _find_ydotool_socket()
        if socket_path:
            # The daemon creates its virtual keyboard right after the socket;
            # give the compositor a moment to pick the new device up.
            time.sleep(0.3)
            return socket_path
        time.sleep(0.1)
    print("ydotoold did not create its socket in time "
          "(checked: %s)" % ", ".join(_socket_candidates()))
    return None


def _ydotool_env(socket_path):
    """Environment for ydotool calls, pinned to the socket we found."""
    env = os.environ.copy()
    env["YDOTOOL_SOCKET"] = socket_path
    return env


def _shortcut_keycodes(shortcut):
    """Translate "ctrl+shift+v" into ydotool >= 1.0 "<keycode>:<pressed>" args.

    Returns None when the shortcut contains a key this module has no keycode
    for; the caller then falls back to the ydotool 0.1.x key-name syntax.
    """
    parts = [p for p in shortcut.split("+") if p]
    if not parts:
        return None
    modifiers, key = parts[:-1], parts[-1]
    if key not in _KEYCODES:
        return None
    try:
        modifier_codes = [_MODIFIER_KEYCODES[m] for m in modifiers]
    except KeyError:
        return None
    key_code = _KEYCODES[key]
    return (
        [f"{code}:1" for code in modifier_codes]
        + [f"{key_code}:1", f"{key_code}:0"]
        + [f"{code}:0" for code in reversed(modifier_codes)]
    )


def _send_paste_shortcut(socket_path):
    """Press the paste shortcut via ydotool.

    ydotool >= 1.0 understands only raw keycode pairs, 0.1.x understands only
    key names. Try keycodes first and fall back to the name syntax so both
    versions work without probing the version.

    Returns:
        True if one of the syntaxes was accepted.
    """
    env = _ydotool_env(socket_path)
    attempts = []
    keycodes = _shortcut_keycodes(PASTE_SHORTCUT)
    if keycodes:
        attempts.append(keycodes)
    attempts.append([PASTE_SHORTCUT])

    for args in attempts:
        try:
            subprocess.run(
                ["ydotool", "key"] + args,
                check=True,
                timeout=5.0,
                env=env,
            )
            return True
        except subprocess.CalledProcessError:
            continue
    print(f"ydotool rejected the paste shortcut '{PASTE_SHORTCUT}'")
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
    """Place text on the clipboard, paste it, then restore the previous
    clipboard contents (Wayland)."""
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

        socket_path = _ensure_ydotoold()
        if not socket_path:
            # Leave our text on the clipboard so the user can paste manually;
            # do not restore the old contents in that case.
            print("Text is on the clipboard - paste manually with "
                  f"{PASTE_SHORTCUT.title()}.")
            return

        # Small settle time so the clipboard offer is ready before pasting.
        time.sleep(0.05)
        try:
            pasted = _send_paste_shortcut(socket_path)
        except FileNotFoundError:
            print("ydotool not found. Please install: sudo apt install ydotool")
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
