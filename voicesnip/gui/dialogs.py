"""
GUI Dialogs

About dialog and model download information dialogs.
Uses CustomTkinter for a modern look.
"""

import os
import sys
import subprocess
import customtkinter as ctk
import webbrowser
from tkinter import messagebox
from PIL import Image

from ..constants import GITHUB_URL


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller builds."""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_path, relative_path)


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

        if git_output.startswith('v') or '-g' in git_output:
            return git_output
        else:
            return f"dev-{git_output}"
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "dev"


def show_about_dialog(parent):
    """Show About dialog with copyright, license, and GitHub info

    Args:
        parent: Parent window
    """
    # Calculate dimensions first
    base_width = 420
    base_height = 650
    try:
        scaled_width = int(base_width * max(1.0, parent.winfo_fpixels('1i') / 96.0))
        scaled_height = int(base_height * max(1.0, parent.winfo_fpixels('1i') / 96.0))
    except Exception:
        scaled_width = base_width
        scaled_height = base_height

    # Calculate center position
    parent_x = parent.winfo_x()
    parent_y = parent.winfo_y()
    parent_width = parent.winfo_width()
    parent_height = parent.winfo_height()
    x = parent_x + (parent_width - scaled_width) // 2
    y = parent_y + (parent_height - scaled_height) // 2

    # Create About dialog window
    about_window = ctk.CTkToplevel(parent)
    about_window.title("About VoiceSnip")
    about_window.geometry(f"{scaled_width}x{scaled_height}+{x}+{y}")
    about_window.resizable(False, False)
    about_window.transient(parent)

    def create_content():
        """Create dialog content after window is ready"""
        about_window.grab_set()

        # Main frame with padding
        main_frame = ctk.CTkFrame(about_window, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # Logo
        try:
            png_path = get_resource_path(os.path.join("assets", "icons", "app", "voicesnip_icon.png"))
            if os.path.exists(png_path):
                logo_image = ctk.CTkImage(
                    light_image=Image.open(png_path),
                    dark_image=Image.open(png_path),
                    size=(80, 80)
                )
                logo_label = ctk.CTkLabel(main_frame, image=logo_image, text="")
                logo_label.image = logo_image  # Keep reference to prevent garbage collection
                logo_label.pack(pady=(0, 15))
        except Exception:
            pass  # Logo is optional

        # App title
        ctk.CTkLabel(
            main_frame,
            text="VoiceSnip",
            font=ctk.CTkFont(size=28, weight="bold")
        ).pack(pady=(0, 5))

        # Subtitle
        ctk.CTkLabel(
            main_frame,
            text="Push-to-Talk Speech-to-Text",
            font=ctk.CTkFont(size=14)
        ).pack(pady=(0, 15))

        # Version info
        ctk.CTkLabel(
            main_frame,
            text=f"Version: {get_version()}",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray60")
        ).pack(pady=(0, 15))

        # Copyright
        ctk.CTkLabel(
            main_frame,
            text="Copyright (c) Stefan Schmidbauer",
            font=ctk.CTkFont(size=14),
            justify="center"
        ).pack(pady=(0, 10))

        # License
        ctk.CTkLabel(
            main_frame,
            text="License: MIT License",
            font=ctk.CTkFont(size=13),
            text_color=("gray40", "gray60")
        ).pack(pady=(0, 15))

        # GitHub link button
        def open_github():
            webbrowser.open(GITHUB_URL)

        ctk.CTkButton(
            main_frame,
            text="GitHub Repository",
            command=open_github,
            width=180,
            font=ctk.CTkFont(size=14)
        ).pack(pady=(0, 15))

        # Separator
        ctk.CTkFrame(main_frame, height=2, fg_color=("gray70", "gray30")).pack(fill="x", pady=(0, 15))

        # OpenAI Whisper attribution
        ctk.CTkLabel(
            main_frame,
            text="Using OpenAI Whisper\n(MIT License, Copyright (c) 2022 OpenAI)",
            font=ctk.CTkFont(size=12),
            justify="center",
            text_color=("gray50", "gray50")
        ).pack(pady=(0, 8))

        # AI development note
        ctk.CTkLabel(
            main_frame,
            text="Developed with AI assistance\n(Claude/Anthropic)",
            font=ctk.CTkFont(size=12),
            justify="center",
            text_color=("gray50", "gray50")
        ).pack(pady=(0, 15))

        # Close button
        ctk.CTkButton(
            main_frame,
            text="Close",
            command=about_window.destroy,
            width=140,
            font=ctk.CTkFont(size=14)
        ).pack(pady=(10, 0))

        about_window.lift()
        about_window.focus_force()

    # Delay content creation to ensure window is ready
    about_window.after(100, create_content)


def show_model_download_info(parent, model):
    """Show info dialog about model download

    Args:
        parent: Parent window (unused, kept for API compatibility)
        model: Model name to display
    """
    info_text = (
        f"The Whisper model '{model}' needs to be downloaded on first use.\n\n"
        "This will happen automatically when you press the hotkey for the first time.\n\n"
        "Larger models can take a long time to download. Please be patient.\n\n"
        "You will see 'Processing...' while the model is being downloaded and loaded."
    )
    messagebox.showinfo("Model Download Required", info_text)
