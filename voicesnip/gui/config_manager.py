"""
GUI Configuration Manager

Handles loading and saving GUI configuration.
"""

import json
import sys
import os
from pathlib import Path
from configparser import ConfigParser

from ..constants import CONFIG_DIR, CONFIG_FILE


def load_config():
    """Load configuration from file

    Returns:
        dict: Configuration dictionary
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: config.json is corrupted, resetting to defaults: {e}")
        except (IOError, OSError) as e:
            print(f"Warning: Could not read config: {e}")
    return {}


def save_config(config):
    """Save configuration to file

    Args:
        config: Configuration dictionary to save
    """
    try:
        # Create config directory if it doesn't exist
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except (IOError, OSError) as e:
        print(f"Error saving config: {e}")


def load_installation_config():
    """Load and validate installation config.

    Returns:
        Dict with config data or None if missing
    """
    # Use platform-aware config directory
    config_file = CONFIG_DIR / 'installation_profile.ini'

    if not config_file.exists():
        return None

    try:
        config = ConfigParser()
        config.read(config_file)

        # Validate required fields
        if 'installation' not in config:
            raise ValueError("Missing [installation] section")

        profile = config['installation'].get('profile')
        features = config['installation'].get('features', '').split(',')

        if not profile or not features:
            raise ValueError("Invalid config: missing profile or features")

        return {
            'profile': profile,
            'features': features,
            'install_date': config['installation'].get('install_date', 'unknown'),
        }

    except Exception as e:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Configuration Error",
            f"Invalid installation config: {e}\n\n"
            "Please run the installer to fix:\n"
            "  ./install.py --force"
        )
        root.destroy()
        return None
