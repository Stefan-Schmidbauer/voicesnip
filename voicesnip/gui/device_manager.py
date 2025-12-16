"""
GUI Device Manager

Handles audio device detection, filtering, and display name formatting.
"""

import sounddevice as sd

from ..constants import COMMON_SAMPLE_RATES


def is_physical_device(device_name):
    """Check if device is a physical microphone (not virtual/system device)"""
    device_lower = device_name.lower()

    # Exclude only virtual/system devices that are NOT physical hardware
    exclude_exact = [
        'pipewire',
        'default',
    ]

    # Exclude devices that match these patterns exactly
    for keyword in exclude_exact:
        if device_lower == keyword:
            return False

    # Exclude devices with monitor/loopback in name
    exclude_keywords = [
        'monitor',
        'loopback',
    ]

    for keyword in exclude_keywords:
        if keyword in device_lower:
            return False

    # Include all devices with hardware identifier (hw:)
    if 'hw:' in device_lower:
        return True

    # Also include known physical device patterns
    include_indicators = [
        'usb audio',
        'røde',
        'rode',
        'videomic',
        'blue',
        'shure',
        'audio-technica',
        'samson',
        'focusrite',
        'scarlett',
        'behringer',
    ]

    for indicator in include_indicators:
        if indicator in device_lower:
            return True

    # Default: exclude unknown devices to be safe
    return False


def format_device_name(name, sample_rate):
    """Format device name for better readability"""
    # Extract meaningful part from technical names
    if ":" in name and "hw:" in name:
        # Handle ALSA names like "USB Audio: - (hw:3,0)" or "HD-Audio Generic: ALC257 Analog (hw:1,0)"
        parts = name.split(":")
        if len(parts) >= 2:
            main_name = parts[0].strip()

            # Check if there's a descriptive second part (not just "-")
            second_part = parts[1].strip()
            if second_part and second_part != "-":
                # Extract the part before (hw:...)
                if "(" in second_part:
                    second_part = second_part.split("(")[0].strip()
                if second_part:
                    return f"{main_name}: {second_part} ({sample_rate}Hz)"

            # Just use the main name if second part is empty or "-"
            return f"{main_name} ({sample_rate}Hz)"

    # Special handling for common names
    if name == "default":
        return f"Default Microphone ({sample_rate}Hz)"
    elif name == "pipewire":
        return f"PipeWire ({sample_rate}Hz)"
    elif "VideoMic" in name or "RØDE" in name:
        # Extract brand/model names
        return f"{name.split(':')[0]} ({sample_rate}Hz)"

    # For long names, try to shorten
    if len(name) > 40:
        return f"{name[:37]}... ({sample_rate}Hz)"

    return f"{name} ({sample_rate}Hz)"


def find_best_sample_rate(device_id):
    """Find best supported sample rate for device"""
    # Try common sample rates in order of preference
    for rate in COMMON_SAMPLE_RATES:
        try:
            sd.check_input_settings(device=device_id, samplerate=rate)
            return rate
        except (sd.PortAudioError, OSError, ValueError):
            continue
    # Fallback
    return 44100


def populate_devices():
    """Get available audio input devices

    Returns:
        tuple: (device_list, display_names) where device_list contains
               (device_id, device_name, sample_rate) tuples
    """
    devices = sd.query_devices()
    device_list = []
    display_names = []
    all_input_devices = []  # Fallback: store all input devices
    default_device_info = None

    # Get the default input device
    try:
        default_device_info = sd.query_devices(kind='input')
        default_idx = default_device_info['index'] if isinstance(default_device_info, dict) else None
    except (sd.PortAudioError, OSError, KeyError):
        default_idx = None

    for idx, device in enumerate(devices):
        name = device['name']
        is_input = device['max_input_channels'] > 0

        # Only show devices with input channels
        if not is_input:
            continue

        # Store all input devices as fallback
        try:
            best_rate = find_best_sample_rate(idx)
        except (sd.PortAudioError, OSError):
            best_rate = 48000  # Default fallback

        all_input_devices.append((idx, name, best_rate))

        # ALWAYS include the default device, even if it's not "physical"
        if idx == default_idx:
            display_name = format_device_name(name, best_rate)
            device_list.append((idx, name, best_rate))
            display_names.append(display_name)
            continue

        # Filter to only show physical devices
        if not is_physical_device(name):
            continue

        # Shorten name for better readability
        display_name = format_device_name(name, best_rate)
        device_list.append((idx, name, best_rate))
        display_names.append(display_name)

    # Fallback: If no physical devices found, use all input devices
    if not device_list and all_input_devices:
        for idx, name, best_rate in all_input_devices:
            display_name = format_device_name(name, best_rate)
            device_list.append((idx, name, best_rate))
            display_names.append(display_name)

    return device_list, display_names, default_idx
