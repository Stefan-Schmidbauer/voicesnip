# VoiceSnip - Push-to-Talk Speech-to-Text

Local push-to-talk speech-to-text for Linux. Hold a hotkey, speak, release - text appears at your cursor.

All processing happens locally on your GPU. No cloud, no server, no data leaves your machine.

![VoiceSnip GUI](voicesnip.png)

## Features

- **Push-to-Talk**: Hold hotkey to record, release to transcribe
- **Local GPU Processing**: Whisper runs directly on your NVIDIA (CUDA) or AMD (ROCm) GPU
- **Privacy-First**: All data stays on your device
- **Configurable Hotkeys**: Any key combination (Ctrl+Space, Alt+R, etc.)
- **Multi-Language**: 10 languages (German, English, French, Spanish, etc.) + Auto-Detection
- **Dark/Light Mode**: Switch between dark and light themes
- **Adjustable Font Size**: A-/A+ buttons to customize text size

## Requirements

- Linux (X11 or Wayland)
- Python 3.8+
- NVIDIA GPU with CUDA **or** AMD GPU with ROCm
- Debian/Ubuntu for automated system package install

## Installation

```bash
git clone https://github.com/Stefan-Schmidbauer/voicesnip.git
cd voicesnip
./install.py
```

The installer will ask you to choose a profile:

| Profile  | Description                                              |
| -------- | -------------------------------------------------------- |
| **cuda** | Whisper with NVIDIA GPU acceleration (requires CUDA)     |
| **rocm** | Whisper with AMD GPU acceleration (requires ROCm, Linux) |

### GPU Setup

**NVIDIA (CUDA):** Install [NVIDIA drivers](https://developer.nvidia.com/cuda-downloads). CUDA libraries are installed automatically by the installer.

**AMD (ROCm):** Install [ROCm drivers](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/) first. PyTorch ROCm is installed automatically by the installer.

## Usage

```bash
./start.sh
```

1. Select your microphone
2. Click "Start"
3. Hold your hotkey (default: Ctrl+Space) and speak
4. Release - text appears at your cursor

## Wayland Support

VoiceSnip provides the same workflow on both X11 and Wayland — hold your hotkey
anywhere, speak, release, and the text appears at your cursor. The display
server is detected at runtime; the difference is purely internal.

### X11

- **Global hotkey** via pynput
- Text is typed at your cursor via `xdotool`

### Wayland

Wayland's compositor blocks the usual global keyboard hook and synthetic typing,
so VoiceSnip uses two lower-level mechanisms instead:

- **Global hotkey** by reading `/dev/input/event*` directly (`python-evdev`).
  This requires your user to be in the **`input`** group.
- Text is inserted by copying it to the clipboard and pasting with **Ctrl+V**
  via `ydotool` (which needs access to `/dev/uinput`).

The installer sets both up for you: it adds you to the `input` group and
installs a udev rule for `/dev/uinput`. **Group changes only take effect after
the next login**, so log out and back in (or reboot) once after installing,
then the hotkey works system-wide just like on X11.

> **Clipboard note:** On Wayland, text is inserted by placing it on the
> clipboard, pasting it, and then restoring your previous clipboard contents.
> Only the **primary clipboard format** is restored — content that advertises
> multiple formats at once (e.g. rich text with `text/html` + `text/plain`, or
> images offering several types) keeps just the primary type; the other formats
> are dropped. This is a limitation of restoring a clipboard offer with
> `wl-copy`, which handles one MIME type per entry.

## Whisper Models

| Model    | Size   | VRAM   | Notes                   |
| -------- | ------ | ------ | ----------------------- |
| tiny     | 78 MB  | 230 MB | Fastest, lowest quality |
| base     | 149 MB | 330 MB |                         |
| small    | 488 MB | 745 MB | Good balance            |
| medium   | 1.5 GB | 2 GB   |                         |
| turbo    | 1.6 GB | 2.2 GB | **Recommended for GPU** |
| large-v3 | 3.1 GB | 3.9 GB | Best quality            |

Models download automatically on first use to `~/.cache/huggingface/`.

## Configuration

Settings are saved automatically in the project directory:

| File                    | Purpose              |
| ----------------------- | -------------------- |
| `.env`                  | Environment config   |
| `voicesnip_config.json` | GUI settings         |
| `voicesnip_profile.ini` | Installation profile |

## License

MIT License - see LICENSE file.

**Third-Party:** OpenAI Whisper (MIT), NVIDIA CUDA, AMD ROCm

## Author

Stefan Schmidbauer

---

_Developed with AI assistance (Claude/Anthropic)_
