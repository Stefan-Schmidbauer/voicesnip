"""
Evdev-based global key listener (Wayland)

pynput's global keyboard listener relies on X11 and cannot capture keys under
Wayland. This module reads /dev/input/event* directly via python-evdev and
translates each event into the same pynput key objects pynput would emit, so it
is a drop-in replacement for ``pynput.keyboard.Listener``: same
``on_press``/``on_release`` callbacks, same ``start()``/``stop()``.

Because it emits pynput key objects, the existing HotkeyManager and
``format_hotkey`` logic work unchanged on both X11 and Wayland.

Requires read access to /dev/input/event* (membership in the 'input' group).
"""

import getpass
import grp
import os
import select
import threading

try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover - handled at runtime
    evdev = None
    ecodes = None

from pynput import keyboard


def input_group_status():
    """Classify the running session's 'input' group membership.

    Reading /dev/input/event* requires the process to *effectively* belong to
    the 'input' group. The common Wayland pitfall: the installer added the user
    to the group (so it shows up in the group database), but the current login
    session predates that change and therefore still lacks it -- the database
    and the live session credentials disagree. We distinguish those so we can
    tell the user to re-login instead of pointing them at the installer again.

    Returns a tuple ``(status, message)`` where status is one of:
        'ok'      -- group is active in this session
        'relogin' -- user is in the group database but must log out/in
        'missing' -- user is not in the group at all (installer not run)
    """
    try:
        input_gid = grp.getgrnam('input').gr_gid
    except KeyError:
        return 'missing', (
            "The 'input' group does not exist on this system. Re-run the "
            "VoiceSnip installer to set up Wayland input permissions."
        )

    if input_gid in os.getgroups():
        return 'ok', (
            "Your user is in the 'input' group, but no keyboard devices under "
            "/dev/input were readable. Check that /dev/input/event* exist."
        )

    try:
        user = getpass.getuser()
    except Exception:
        user = ''
    try:
        in_db = user in set(grp.getgrgid(input_gid).gr_mem)
    except KeyError:
        in_db = False

    if in_db:
        return 'relogin', (
            "You have been added to the 'input' group, but this login session "
            "started before that change, so it is not active yet.\n\n"
            "Log out and back in (or reboot), then start VoiceSnip again."
        )

    return 'missing', (
        "Your user is not in the 'input' group, which VoiceSnip needs to read "
        "keyboard events for the global hotkey under Wayland.\n\n"
        "Re-run the VoiceSnip installer to set this up, then log out and back in."
    )


def _build_keycode_map():
    """Map evdev key codes -> pynput key objects (built once)."""
    if ecodes is None:
        return {}

    mapping = {
        # Modifiers. Keep left/right variants -- HotkeyManager.normalize_key
        # folds them to the generic form, exactly as for pynput input.
        ecodes.KEY_LEFTCTRL: keyboard.Key.ctrl_l,
        ecodes.KEY_RIGHTCTRL: keyboard.Key.ctrl_r,
        ecodes.KEY_LEFTALT: keyboard.Key.alt_l,
        ecodes.KEY_RIGHTALT: keyboard.Key.alt_r,
        ecodes.KEY_LEFTSHIFT: keyboard.Key.shift_l,
        ecodes.KEY_RIGHTSHIFT: keyboard.Key.shift_r,
        ecodes.KEY_LEFTMETA: keyboard.Key.cmd_l,
        ecodes.KEY_RIGHTMETA: keyboard.Key.cmd_r,
    }

    # Special keys (mirror the names supported in constants.KEY_MAP)
    specials = {
        'KEY_SPACE': keyboard.Key.space,
        'KEY_ENTER': keyboard.Key.enter,
        'KEY_TAB': keyboard.Key.tab,
        'KEY_ESC': keyboard.Key.esc,
        'KEY_BACKSPACE': keyboard.Key.backspace,
        'KEY_DELETE': keyboard.Key.delete,
        'KEY_INSERT': keyboard.Key.insert,
        'KEY_HOME': keyboard.Key.home,
        'KEY_END': keyboard.Key.end,
        'KEY_PAGEUP': keyboard.Key.page_up,
        'KEY_PAGEDOWN': keyboard.Key.page_down,
        'KEY_UP': keyboard.Key.up,
        'KEY_DOWN': keyboard.Key.down,
        'KEY_LEFT': keyboard.Key.left,
        'KEY_RIGHT': keyboard.Key.right,
        'KEY_CAPSLOCK': keyboard.Key.caps_lock,
    }
    for name, key_obj in specials.items():
        code = getattr(ecodes, name, None)
        if code is not None:
            mapping[code] = key_obj

    # Function keys F1..F12
    for i in range(1, 13):
        code = getattr(ecodes, f'KEY_F{i}', None)
        key_obj = getattr(keyboard.Key, f'f{i}', None)
        if code is not None and key_obj is not None:
            mapping[code] = key_obj

    # Letters a-z and digits 0-9 -> character KeyCodes (lowercase, matching
    # how hotkeys are stored, e.g. "ctrl+r").
    for ch in 'abcdefghijklmnopqrstuvwxyz0123456789':
        code = getattr(ecodes, f'KEY_{ch.upper()}', None)
        if code is not None:
            mapping[code] = keyboard.KeyCode.from_char(ch)

    return mapping


class EvdevError(RuntimeError):
    """Raised when the evdev backend cannot be used (no evdev, no permission)."""


class EvdevKeyListener:
    """Drop-in replacement for ``pynput.keyboard.Listener`` using evdev.

    Args:
        on_press: callable(key) invoked on key-down with a pynput key object.
        on_release: callable(key) invoked on key-up with a pynput key object.
    """

    def __init__(self, on_press=None, on_release=None):
        if evdev is None:
            raise EvdevError(
                "python-evdev is not installed (required for Wayland hotkeys). "
                "Install it with: sudo apt install python3-evdev"
            )
        self._on_press = on_press
        self._on_release = on_release
        self._keycode_map = _build_keycode_map()
        self._devices = []
        self._stop = threading.Event()
        self._thread = None
        # Accepted for API compatibility with pynput.keyboard.Listener.
        self.daemon = True

    def _find_keyboards(self):
        """Return open InputDevices that look like real keyboards."""
        keyboards = []
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except (PermissionError, OSError):
                continue
            caps = dev.capabilities().get(ecodes.EV_KEY, [])
            # A real keyboard exposes SPACE and at least one letter key.
            if ecodes.KEY_SPACE in caps and ecodes.KEY_A in caps:
                keyboards.append(dev)
            else:
                dev.close()
        return keyboards

    def start(self):
        """Start reading keyboards in a background thread.

        Raises:
            EvdevError: if no readable keyboard devices are found (usually a
                missing 'input' group membership).
        """
        self._devices = self._find_keyboards()
        if not self._devices:
            _, hint = input_group_status()
            raise EvdevError(
                "No readable keyboard devices found under /dev/input.\n\n" + hint
            )
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        fd_to_dev = {dev.fd: dev for dev in self._devices}
        while not self._stop.is_set():
            try:
                readable, _, _ = select.select(fd_to_dev, [], [], 0.5)
            except (OSError, ValueError):
                break
            for fd in readable:
                dev = fd_to_dev.get(fd)
                if dev is None:
                    continue
                try:
                    for event in dev.read():
                        if event.type == ecodes.EV_KEY:
                            self._dispatch(event)
                except OSError:
                    # Device disappeared (e.g. unplugged) -- close it and stop
                    # reading. Removing it from self._devices releases the fd
                    # now instead of leaking it until stop(), and avoids a
                    # redundant close there.
                    dead = fd_to_dev.pop(fd, None)
                    if dead is not None:
                        try:
                            dead.close()
                        except OSError:
                            pass
                        if dead in self._devices:
                            self._devices.remove(dead)

    def _dispatch(self, event):
        key = self._keycode_map.get(event.code)
        if key is None:
            return
        # event.value: 1 = key down, 0 = key up, 2 = autorepeat (ignored).
        if event.value == 1 and self._on_press:
            try:
                self._on_press(key)
            except Exception:
                pass
        elif event.value == 0 and self._on_release:
            try:
                self._on_release(key)
            except Exception:
                pass

    def stop(self):
        """Stop the listener and release all devices."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        for dev in self._devices:
            try:
                dev.close()
            except Exception:
                pass
        self._devices = []
