"""
GUI Device Manager

Handles audio device detection, filtering, and display name formatting.
Supports PipeWire/PulseAudio on Linux (proper device descriptions) with
fallback to sounddevice/PortAudio enumeration on other platforms.
"""

import subprocess

import sounddevice as sd

from ..constants import COMMON_SAMPLE_RATES


def _get_pulseaudio_sources():
    """Query PulseAudio/PipeWire for available input sources.

    Parses `pactl list sources` output to get source names, descriptions,
    and sample rates. Filters out monitor sources (output captures).

    Returns:
        List of (source_name, description, sample_rate) tuples, or None if unavailable.
    """
    try:
        import os
        env = os.environ.copy()
        env['LANG'] = 'C'
        result = subprocess.run(
            ['pactl', 'list', 'sources'],
            capture_output=True, text=True, timeout=5, env=env
        )
        if result.returncode != 0:
            return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    sources = []
    current = {}

    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith('Source #'):
            if current.get('name'):
                sources.append(current)
            current = {}
        elif stripped.startswith('Name:'):
            current['name'] = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('Description:'):
            current['description'] = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('Sample Specification:'):
            # Parse e.g. "s32le 2ch 48000Hz"
            spec = stripped.split(':', 1)[1].strip()
            for part in spec.split():
                if part.endswith('Hz'):
                    try:
                        current['sample_rate'] = int(part[:-2])
                    except ValueError:
                        pass

    if current.get('name'):
        sources.append(current)

    # Filter: only actual input sources, not output monitors
    input_sources = []
    for src in sources:
        name = src.get('name', '')
        desc = src.get('description', '')
        rate = src.get('sample_rate', 48000)

        if '.monitor' in name or desc.lower().startswith('monitor of'):
            continue

        input_sources.append((name, desc, rate))

    return input_sources if input_sources else None


def _get_default_pulseaudio_source():
    """Get the current default PulseAudio/PipeWire source name.

    Returns:
        Source name string, or None if unavailable.
    """
    try:
        result = subprocess.run(
            ['pactl', 'get-default-source'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def set_pulseaudio_source(source_name):
    """Set the default PulseAudio/PipeWire input source.

    Called before recording to route the user-selected microphone
    through sounddevice's default device.

    Args:
        source_name: PulseAudio source name to set as default.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ['pactl', 'set-default-source', source_name],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def find_best_sample_rate(device_id):
    """Find best supported sample rate for a sounddevice device."""
    for rate in COMMON_SAMPLE_RATES:
        try:
            sd.check_input_settings(device=device_id, samplerate=rate)
            return rate
        except (sd.PortAudioError, OSError, ValueError):
            continue
    return 44100


def populate_devices():
    """Get available audio input devices.

    Tries PipeWire/PulseAudio first for proper device descriptions
    (matching what Linux Settings shows), falls back to sounddevice
    enumeration on non-PipeWire systems.

    Returns:
        tuple: (device_list, display_names, default_source_id)

        device_list contains (device_id, device_name, sample_rate) tuples where:
        - device_id: PulseAudio source name (str) or sounddevice index (int)
        - device_name: Identifier for config persistence
        - sample_rate: Recording sample rate
        - default_source_id: PA source name (str) or sounddevice index (int)
    """
    # Try PulseAudio/PipeWire first (Linux with PipeWire/PulseAudio)
    pa_sources = _get_pulseaudio_sources()
    if pa_sources:
        device_list = []
        display_names = []

        # Get default source for pre-selection
        default_source = _get_default_pulseaudio_source()

        # Find sample rate for the default sounddevice device (used for recording)
        try:
            default_rate = find_best_sample_rate(None)
        except Exception:
            default_rate = 48000

        for name, description, _native_rate in pa_sources:
            device_list.append((name, name, default_rate))
            display_names.append(description)

        return device_list, display_names, default_source

    # Fallback: sounddevice enumeration (Windows, macOS, non-PipeWire Linux)
    return _populate_devices_sounddevice()


def _populate_devices_sounddevice():
    """Fallback: enumerate devices via sounddevice/PortAudio."""
    devices = sd.query_devices()
    device_list = []
    display_names = []
    all_input_devices = []

    try:
        default_device_info = sd.query_devices(kind='input')
        default_idx = default_device_info['index'] if isinstance(default_device_info, dict) else None
    except (sd.PortAudioError, OSError, KeyError):
        default_idx = None

    for idx, device in enumerate(devices):
        name = device['name']
        if device['max_input_channels'] <= 0:
            continue

        try:
            best_rate = find_best_sample_rate(idx)
        except (sd.PortAudioError, OSError):
            best_rate = 48000

        all_input_devices.append((idx, name, best_rate))

        # Always include the system default device
        if idx == default_idx:
            display_name = _format_device_name_alsa(name, best_rate)
            device_list.append((idx, name, best_rate))
            display_names.append(display_name)
            continue

        # Filter out virtual/system devices
        if not _is_physical_device(name):
            continue

        display_name = _format_device_name_alsa(name, best_rate)
        device_list.append((idx, name, best_rate))
        display_names.append(display_name)

    # Fallback: if no physical devices found, show all input devices
    if not device_list and all_input_devices:
        for idx, name, best_rate in all_input_devices:
            display_name = _format_device_name_alsa(name, best_rate)
            device_list.append((idx, name, best_rate))
            display_names.append(display_name)

    return device_list, display_names, default_idx


def _is_physical_device(device_name):
    """Check if device is a physical microphone (blocklist approach)."""
    device_lower = device_name.lower()

    exclude_exact = ['pipewire', 'default']
    for keyword in exclude_exact:
        if device_lower == keyword:
            return False

    exclude_keywords = ['monitor', 'loopback']
    for keyword in exclude_keywords:
        if keyword in device_lower:
            return False

    return True


def _format_device_name_alsa(name, sample_rate):
    """Format ALSA device name for display (sounddevice fallback path)."""
    if ":" in name and "hw:" in name:
        parts = name.split(":")
        if len(parts) >= 2:
            main_name = parts[0].strip()
            second_part = parts[1].strip()
            if second_part and second_part != "-":
                if "(" in second_part:
                    second_part = second_part.split("(")[0].strip()
                if second_part:
                    return f"{main_name}: {second_part} ({sample_rate}Hz)"
            return f"{main_name} ({sample_rate}Hz)"

    if name == "default":
        return f"Default Microphone ({sample_rate}Hz)"
    elif name == "pipewire":
        return f"PipeWire ({sample_rate}Hz)"

    if len(name) > 40:
        return f"{name[:37]}... ({sample_rate}Hz)"

    return f"{name} ({sample_rate}Hz)"
