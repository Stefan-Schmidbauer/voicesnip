# VoiceSnip - Push-to-Talk Speech-to-Text

Push-to-Talk Speech-to-Text for Linux and Windows. Hold a hotkey, speak, release - text appears at your cursor.

![VoiceSnip GUI](voicesnip.png)

## Features

- **Push-to-Talk**: Hold hotkey to record, release to transcribe
- **Multiple Providers**: Local Whisper (CPU/GPU), Faster Whisper Server, Speaches Server, or Deepgram Cloud
- **Privacy-First**: Local Whisper keeps all data on your device
- **GPU Acceleration**: Much faster with NVIDIA (CUDA) or AMD (ROCm) GPU
- **Configurable Hotkeys**: Any key combination (Ctrl+Space, Alt+R, etc.)
- **Multi-Language**: 10 languages (German, English, French, Spanish, etc.) + Auto-Detection
- **Dark/Light Mode**: Switch between dark and light themes
- **Adjustable Font Size**: A-/A+ buttons to customize text size
- **Team/Server Mode**: Connect multiple clients to a central [Speaches](https://speaches.ai) server for team-wide speech-to-text

## Download

Download the latest release for your platform:

| Platform | Download |
|----------|----------|
| **Windows** | [VoiceSnip-Windows.zip](https://github.com/Stefan-Schmidbauer/voicesnip/releases/latest) |
| **Linux** | [VoiceSnip-Linux.tar.gz](https://github.com/Stefan-Schmidbauer/voicesnip/releases/latest) |

These builds include local transcription (Whisper CPU), Faster Whisper Server, Speaches Server, and Deepgram Cloud support. GPU acceleration (CUDA) is also available if CUDA is installed on your system.

> **GPU Acceleration:** The pre-built binaries support CUDA if you install NVIDIA CUDA 12 + cuDNN manually. For automatic CUDA setup, use the [source installation](#installation-from-source) with `--profile cuda`. If no GPU is available, select "Whisper Local CPU".

## Quick Start

### 1. Extract & Run

**Windows:**
```
1. Extract ZIP
2. Run VoiceSnip.exe
```

> **Note:** Windows may show an "Unknown publisher" warning. Click **"More info"** → **"Run anyway"**. This is normal for unsigned open-source software.

**Linux:**
```bash
tar -xzf VoiceSnip-Linux.tar.gz
chmod +x VoiceSnip-Linux.AppImage
./VoiceSnip-Linux.AppImage
```

### 2. Configure (Optional)

For **Deepgram Cloud**, **Speaches Server**, or **Faster Whisper Server**, edit `voicesnip.ini`:

```ini
DEEPGRAM_API_KEY=your_api_key_here
DEEPGRAM_ENDPOINT=https://api.deepgram.com/v1/listen

# For Speaches Server:
SPEACHES_ENDPOINT=http://your-server:8000/v1/audio/transcriptions
SPEACHES_MODEL=Systran/faster-whisper-large-v3

# For Faster Whisper Server (model configured on server):
FASTER_WHISPER_ENDPOINT=http://your-server:8000/v1/audio/transcriptions
```

**Note:** Local Whisper works without any configuration!

### 3. Use

1. Select microphone and provider
2. Click "Start"
3. Hold your hotkey (default: Ctrl+Space) and speak
4. Release - text appears at cursor

---

## Wayland Support

VoiceSnip works on both X11 and Wayland, but with different workflows due to Wayland's security model.

### X11 (Full Support)

- **Global hotkeys work** - Hold Ctrl+Space (or your configured hotkey) anywhere
- Text is automatically inserted at your cursor

### Wayland (GUI-Based Recording)

Wayland blocks global keyboard hooks for security reasons. VoiceSnip provides an alternative workflow:

1. **Click "Start"** to activate VoiceSnip
2. **Click "Start Recording"** button in the GUI (instead of hotkey)
3. Speak your text
4. **Click "Stop Recording"** (or click the button again)
5. Text appears in the transcription field
6. **Enable "Auto-copy to clipboard"** for automatic copying
7. Switch to your target app and **Ctrl+V** to paste

**Tip:** Enable "Auto-copy to clipboard" to minimize steps under Wayland.

---

# For Developers

## Installation from Source

### Requirements

- Python 3.8+
- Linux: X11 or Wayland (see [Wayland Support](#wayland-support)), Debian/Ubuntu for automated install
- Windows: Python from [python.org](https://www.python.org/downloads/)
- For NVIDIA GPU: NVIDIA GPU with CUDA drivers
- For AMD GPU: AMD GPU with ROCm drivers

### Install

```bash
git clone https://github.com/Stefan-Schmidbauer/voicesnip.git
cd voicesnip
./install.py           # Linux
py install.py          # Windows
```

### Installation Profiles

| Profile | Description |
|---------|-------------|
| **basis** | Whisper CPU + Deepgram + Speaches + Faster Whisper Server |
| **cuda** | Whisper CPU/GPU + Deepgram + Speaches + Faster Whisper Server<br>(requires NVIDIA GPU) |
| **rocm** | Whisper CPU/GPU + Deepgram + Speaches + Faster Whisper Server<br>(requires AMD GPU with ROCm, Linux only) |

### Run

```bash
./start.sh             # Linux
start.bat              # Windows
```

### GPU Acceleration (CUDA)

For pre-built downloads or manual installation, install [CUDA Toolkit 12](https://developer.nvidia.com/cuda-downloads) and [cuDNN](https://developer.nvidia.com/cudnn-downloads).

When using `install.py --profile cuda`, CUDA libraries are installed automatically via pip. Only the NVIDIA driver is required.

### GPU Acceleration (ROCm)

For AMD GPUs, install [ROCm](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/) drivers first.

When using `install.py --profile rocm`, PyTorch ROCm is installed automatically. Only the ROCm driver is required. Linux only.

## Provider Comparison

| Provider | Cost | Requirements | Privacy | Best for |
|----------|------|--------------|---------|----------|
| **Whisper Local CPU** | Free | None | Local | Privacy, offline |
| **Whisper Local GPU (CUDA)** | Free | NVIDIA + CUDA | Local | Speed + Privacy (NVIDIA) |
| **Whisper Local GPU (ROCm)** | Free | AMD + ROCm | Local | Speed + Privacy (AMD) |
| **Faster Whisper Server** | Free | Running server | Local/Network | Fixed server model |
| **Speaches Server** | Free | Running server | Local/Network | GPU sharing, model selection |
| **Deepgram Cloud** | [Pricing](https://deepgram.com/pricing) | API key, Internet | Cloud | Fastest setup |

## Speaches Server

For teams or multi-device setups, you can run a central Speaches server and connect multiple VoiceSnip clients to it. This allows sharing a single GPU across your network while keeping all data on your own infrastructure.

[Speaches](https://speaches.ai) is an OpenAI API-compatible server with GPU acceleration support. See the [Speaches Documentation](https://speaches.ai) for installation instructions via Docker or from source.

Configure VoiceSnip clients by setting `SPEACHES_ENDPOINT` and `SPEACHES_MODEL` in `voicesnip.ini` to point to your server. The model can also be selected in the GUI — available models are queried from the server automatically.

## Faster Whisper Server

[Faster Whisper Server](https://github.com/fedirz/faster-whisper-server) is a lightweight, OpenAI API-compatible server for Faster Whisper. The model is configured on the server itself — VoiceSnip sends audio and receives text without selecting a model.

This provider also works with [insanely-fast-whisper-rocm](https://github.com/beecave-homelab/insanely-fast-whisper-rocm) for AMD GPU servers (same OpenAI-compatible API).

Configure VoiceSnip by setting `FASTER_WHISPER_ENDPOINT` in `voicesnip.ini`. No model selection is needed in the GUI (the dropdown shows "N/A").

## Whisper Models

| Model | Size | VRAM | Notes |
|-------|------|------|-------|
| tiny | 78 MB | 230 MB | Fastest, lowest quality |
| base | 149 MB | 330 MB | |
| small | 488 MB | 745 MB | **Recommended for CPU** |
| medium | 1.5 GB | 2 GB | |
| turbo | 1.6 GB | 2.2 GB | **Recommended for GPU** |
| large-v3 | 3.1 GB | 3.9 GB | Best quality |

Models download automatically on first use.

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| `voicesnip.ini` | Installation dir | API keys |
| `voicesnip_config.json` | Installation dir | GUI settings |
| `voicesnip_profile.ini` | Installation dir | Installation profile |
| Whisper models | `~/.cache/huggingface/` | Downloaded models |

## Advanced Configuration

### Speaches Server

| Variable | Required | Description |
|----------|----------|-------------|
| `SPEACHES_ENDPOINT` | Yes | API URL, e.g. `http://your-server:8000/v1/audio/transcriptions` |
| `SPEACHES_MODEL` | Yes | Hugging Face model name, e.g. `Systran/faster-whisper-large-v3` |
| `SPEACHES_API_KEY` | No | Bearer token for authenticated servers |
| `SPEACHES_VERIFY_SSL` | No | Set to `false` for self-signed certificates |
| `SPEACHES_ALLOWED_MODELS` | No | Comma-separated list to restrict the model dropdown |

### Faster Whisper Server

| Variable | Required | Description |
|----------|----------|-------------|
| `FASTER_WHISPER_ENDPOINT` | Yes | API URL, e.g. `http://your-server:8000/v1/audio/transcriptions` |
| `FASTER_WHISPER_API_KEY` | No | Bearer token for authenticated servers |
| `FASTER_WHISPER_VERIFY_SSL` | No | Set to `false` for self-signed certificates |

## Provider Architecture (Developer Reference)

VoiceSnip uses a generic, self-describing provider registry. Adding a new STT provider requires no changes to the GUI code. See [docs/PROVIDERS.md](docs/PROVIDERS.md) for the full developer guide.

## License

MIT License - see LICENSE file.

**Third-Party:** OpenAI Whisper (MIT), Deepgram API, NVIDIA CUDA, AMD ROCm

## Author

Stefan Schmidbauer

---

*Developed with AI assistance (Claude/Anthropic)*
