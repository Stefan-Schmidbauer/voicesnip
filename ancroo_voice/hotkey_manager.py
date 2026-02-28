"""
Hotkey Management

Handles hotkey parsing, normalization, and detection logic.
"""

import threading
from pynput import keyboard

from .constants import KEY_MAP, KEY_NAME_MAP, DEFAULT_HOTKEY


class HotkeyManager:
    """Manages hotkey configuration and detection"""

    def __init__(self, hotkey_str=DEFAULT_HOTKEY):
        self.hotkey_config = self.parse_hotkey(hotkey_str)
        self.pressed_keys = set()
        self.pressed_keys_lock = threading.Lock()

    def parse_hotkey(self, hotkey_str):
        """Parse hotkey string (e.g., 'ctrl+space') into key components

        Raises:
            ValueError: If hotkey string is empty or invalid
        """
        # Validate hotkey is not empty
        if not hotkey_str or not hotkey_str.strip():
            raise ValueError("Hotkey cannot be empty")

        parts = [k.strip().lower() for k in hotkey_str.split('+') if k.strip()]

        # Validate we have at least one key after filtering
        if not parts:
            raise ValueError("Invalid hotkey format")

        config = {
            'modifiers': [],
            'trigger_key': None,
            'raw': hotkey_str
        }

        for part in parts:
            if part in ['ctrl', 'control', 'alt', 'shift', 'cmd', 'super']:
                config['modifiers'].append(KEY_MAP[part])
            else:
                # Trigger key (last non-modifier key)
                if part in KEY_MAP:
                    config['trigger_key'] = KEY_MAP[part]
                else:
                    # Single character key
                    try:
                        config['trigger_key'] = keyboard.KeyCode.from_char(part)
                    except (ValueError, AttributeError):
                        config['trigger_key'] = part

        # Validate that we have a trigger key
        if config['trigger_key'] is None:
            raise ValueError(f"Invalid hotkey: no trigger key found in '{hotkey_str}'")

        return config

    def normalize_key(self, key):
        """Normalize key to handle left/right variants of modifier keys"""
        # Map left/right variants to generic form
        key_mapping = {
            keyboard.Key.ctrl_l: keyboard.Key.ctrl,
            keyboard.Key.ctrl_r: keyboard.Key.ctrl,
            keyboard.Key.alt_l: keyboard.Key.alt,
            keyboard.Key.alt_r: keyboard.Key.alt,
            keyboard.Key.shift_l: keyboard.Key.shift,
            keyboard.Key.shift_r: keyboard.Key.shift,
            keyboard.Key.cmd_l: keyboard.Key.cmd,
            keyboard.Key.cmd_r: keyboard.Key.cmd,
        }
        return key_mapping.get(key, key)

    def is_hotkey_pressed(self):
        """Check if the configured hotkey combination is currently pressed"""
        with self.pressed_keys_lock:
            # Check if all modifiers are pressed
            for modifier in self.hotkey_config['modifiers']:
                if modifier not in self.pressed_keys:
                    return False

            # Check if trigger key is pressed
            trigger_key = self.hotkey_config['trigger_key']

            # For KeyCode objects (character keys), compare by char value (case-insensitive)
            if isinstance(trigger_key, keyboard.KeyCode):
                # Get the expected char value (lowercase)
                expected_char = trigger_key.char.lower() if trigger_key.char else None

                # Check if any pressed key has the same char value
                for pressed_key in self.pressed_keys:
                    if isinstance(pressed_key, keyboard.KeyCode) and pressed_key.char:
                        # Compare case-insensitive
                        if pressed_key.char.lower() == expected_char:
                            return True
                return False
            else:
                # For special keys (Key.space, Key.ctrl, etc.), use direct comparison
                if trigger_key not in self.pressed_keys:
                    return False

            return True

    def on_press(self, key):
        """Handle key press events"""
        normalized_key = self.normalize_key(key)
        with self.pressed_keys_lock:
            self.pressed_keys.add(normalized_key)
            # Also add the original key (for character keys)
            self.pressed_keys.add(key)

    def on_release(self, key):
        """Handle key release events"""
        normalized_key = self.normalize_key(key)

        # Remove from pressed keys
        with self.pressed_keys_lock:
            self.pressed_keys.discard(normalized_key)
            self.pressed_keys.discard(key)

    def is_hotkey_part_released(self, key):
        """Check if the released key is part of the configured hotkey"""
        normalized_key = self.normalize_key(key)
        trigger_key = self.hotkey_config['trigger_key']
        all_hotkey_keys = set(self.hotkey_config['modifiers']) | {trigger_key}

        # Check if the released key is part of the hotkey
        if normalized_key in all_hotkey_keys or key in all_hotkey_keys:
            return True

        # For KeyCode objects, compare by char value (case-insensitive)
        if isinstance(trigger_key, keyboard.KeyCode) and isinstance(key, keyboard.KeyCode):
            if trigger_key.char and key.char:
                if key.char.lower() == trigger_key.char.lower():
                    return True

        return False


def format_hotkey(keys):
    """Format a set of keys into a hotkey string

    Args:
        keys: Set of pynput key objects

    Returns:
        Formatted hotkey string (e.g., 'ctrl+alt+r')
    """
    key_names = []
    modifiers = []

    for key in keys:
        if key in KEY_NAME_MAP:
            name = KEY_NAME_MAP[key]
            if name in ['ctrl', 'alt', 'shift', 'cmd']:
                if name not in modifiers:
                    modifiers.append(name)
            else:
                key_names.append(name)
        elif hasattr(key, 'char') and key.char:
            # Check if char is printable (not a control character)
            if key.char.isprintable():
                key_names.append(key.char.lower())
            elif hasattr(key, 'vk') and key.vk:
                # On Windows with modifiers, use virtual key code to get the letter
                # vk codes 65-90 are A-Z
                if 65 <= key.vk <= 90:
                    key_names.append(chr(key.vk).lower())
                else:
                    key_names.append(f'key{key.vk}')
        elif hasattr(key, 'vk') and key.vk:
            # Fallback: use virtual key code
            if 65 <= key.vk <= 90:
                key_names.append(chr(key.vk).lower())
            elif 48 <= key.vk <= 57:
                key_names.append(chr(key.vk))  # 0-9
            else:
                key_names.append(f'key{key.vk}')

    # Sort modifiers consistently
    modifier_order = ['ctrl', 'alt', 'shift', 'cmd']
    modifiers.sort(key=lambda x: modifier_order.index(x) if x in modifier_order else 999)

    # Combine modifiers and key
    all_parts = modifiers + key_names
    return '+'.join(all_parts) if all_parts else DEFAULT_HOTKEY
