"""
GUI Dialogs

About dialog and model download information dialogs.
"""

import subprocess
import tkinter as tk
from tkinter import ttk
import webbrowser

from ..constants import GITHUB_URL


def get_version():
    """Get version from git

    Returns:
        str: Version string (e.g., 'v1.0.0' or 'dev-a1b2c3d')
    """
    try:
        result = subprocess.run(
            ['git', 'describe', '--tags', '--always'],
            capture_output=True,
            text=True,
            check=True,
            timeout=2
        )
        git_output = result.stdout.strip()

        # Check if output is a tag (starts with 'v' or contains '-g')
        # Tags: v1.0.0 or v1.0.0-5-g02c8a48 (tag with commits ahead)
        # Commit-only: 02c8a48
        if git_output.startswith('v') or '-g' in git_output:
            # It's a tag or tag with commits
            return git_output
        else:
            # It's just a commit hash (no tags)
            return f"dev-{git_output}"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "dev"


def show_about_dialog(parent):
    """Show About dialog with copyright, license, and GitHub info

    Args:
        parent: Parent tkinter window
    """
    # Create About dialog window
    about_window = tk.Toplevel(parent)
    about_window.title("About VoiceSnip")

    # Center the window
    about_window.transient(parent)
    about_window.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(about_window, padding="30")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # App title
    title_label = ttk.Label(
        main_frame,
        text="VoiceSnip",
        font=("Arial", 20, "bold")
    )
    title_label.pack(pady=(0, 5))

    # Subtitle
    subtitle_label = ttk.Label(
        main_frame,
        text="Push-to-Talk Speech-to-Text",
        font=("Arial", 10)
    )
    subtitle_label.pack(pady=(0, 20))

    # Version info
    version_label = ttk.Label(
        main_frame,
        text=f"Version: {get_version()}",
        font=("Arial", 9)
    )
    version_label.pack(pady=(0, 20))

    # Copyright
    copyright_label = ttk.Label(
        main_frame,
        text="Copyright (c) 2025\nStefan Schmidbauer",
        font=("Arial", 10),
        justify=tk.CENTER
    )
    copyright_label.pack(pady=(0, 15))

    # License
    license_label = ttk.Label(
        main_frame,
        text="License: MIT License",
        font=("Arial", 9)
    )
    license_label.pack(pady=(0, 20))

    # GitHub link button
    def open_github():
        webbrowser.open(GITHUB_URL)

    github_button = ttk.Button(
        main_frame,
        text="GitHub Repository",
        command=open_github
    )
    github_button.pack(pady=(0, 20))

    # Separator
    separator = ttk.Separator(main_frame, orient=tk.HORIZONTAL)
    separator.pack(fill=tk.X, pady=(0, 20))

    # OpenAI Whisper attribution
    whisper_label = ttk.Label(
        main_frame,
        text="Using OpenAI Whisper\n(MIT License, Copyright (c) 2022 OpenAI)",
        font=("Arial", 8),
        justify=tk.CENTER,
        foreground="gray"
    )
    whisper_label.pack(pady=(0, 10))

    # AI development note
    ai_label = ttk.Label(
        main_frame,
        text="Developed with AI assistance\n(Claude/Anthropic)",
        font=("Arial", 8),
        justify=tk.CENTER,
        foreground="gray"
    )
    ai_label.pack(pady=(0, 20))

    # Close button
    close_button = ttk.Button(
        main_frame,
        text="Close",
        command=about_window.destroy,
        width=15
    )
    close_button.pack(pady=(10, 0))

    # Update window to calculate required size
    about_window.update_idletasks()

    # Calculate width with DPI scaling
    base_width = 450
    scaled_width = int(base_width * max(1.0, parent.winfo_fpixels('1i') / 96.0))

    # Set minimum width and let height adjust automatically
    about_window.minsize(scaled_width, 1)
    about_window.resizable(False, False)


def show_model_download_info(parent, model):
    """Show info dialog about model download

    Args:
        parent: Parent tkinter window
        model: Model name to display
    """
    # Create info dialog window
    info_window = tk.Toplevel(parent)
    info_window.title("Model Download Required")

    # Center the window
    info_window.transient(parent)
    info_window.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(info_window, padding="25")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    title_label = ttk.Label(
        main_frame,
        text="Model Download Required",
        font=("Arial", 12, "bold")
    )
    title_label.pack(pady=(0, 15))

    # Info text with better line wrapping
    info_text = (
        f"The Whisper model '{model}' needs to be downloaded on first use.\n\n"
        "This will happen automatically when you press the hotkey for the first time.\n\n"
        "Larger models can take a long time to download. Please be patient.\n\n"
        "You will see 'Processing...' while the model is being downloaded and loaded."
    )

    # Calculate width with DPI scaling
    base_width = 480
    scaled_width = int(base_width * max(1.0, parent.winfo_fpixels('1i') / 96.0))

    info_label = ttk.Label(
        main_frame,
        text=info_text,
        font=("Arial", 10),
        justify=tk.LEFT,
        wraplength=scaled_width - 50  # Leave margin for padding
    )
    info_label.pack(pady=(0, 20))

    # OK button
    ok_button = ttk.Button(
        main_frame,
        text="OK",
        command=info_window.destroy,
        width=15
    )
    ok_button.pack()

    # Set focus to OK button for easy dismissal with Enter
    ok_button.focus()

    # Update window to calculate required size
    info_window.update_idletasks()

    # Set minimum width and let height adjust automatically
    info_window.minsize(scaled_width, 1)
    info_window.resizable(False, False)
