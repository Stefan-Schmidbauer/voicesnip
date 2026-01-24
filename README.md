# VoiceSnip - Push-to-Talk Speech-to-Text

Push-to-Talk Speech-to-Text for Linux and Windows. Hold a hotkey, speak, release - text appears at your cursor.

![VoiceSnip GUI](voicesnip.png)

## Features

- **Push-to-Talk**: Hold hotkey to record, release to transcribe
- **Multiple Providers**: Local Whisper (CPU/GPU), Faster Whisper Server, or Deepgram Cloud
- **Privacy-First**: Local Whisper keeps all data on your device
- **GPU Acceleration**: Much faster with NVIDIA GPU
- **Configurable Hotkeys**: Any key combination (Ctrl+Space, Alt+R, etc.)
- **Multi-Language**: German, English, or Auto-Detection

## Download

Download the latest release for your platform:

| Platform | CPU Version | GPU Version (NVIDIA) |
|----------|-------------|----------------------|
| **Windows** | [VoiceSnip-Windows.zip](https://github.com/Stefan-Schmidbauer/voicesnip/releases/latest) | [VoiceSnip-Windows-CUDA.zip](https://github.com/Stefan-Schmidbauer/voicesnip/releases/latest) |
| **Linux** | [VoiceSnip-Linux.tar.gz](https://github.com/Stefan-Schmidbauer/voicesnip/releases/latest) | [VoiceSnip-Linux-CUDA.tar.gz](https://github.com/Stefan-Schmidbauer/voicesnip/releases/latest) |

**Which version?**
- **CPU**: Works everywhere, uses processor for transcription
- **CUDA**: Much faster transcription, requires NVIDIA GPU with CUDA installed

## Quick Start

### 1. Extract & Run

**Windows:**
```
1. Extract ZIP
2. Run VoiceSnip.exe
```

**Linux:**
```bash
tar -xzf VoiceSnip-Linux*.tar.gz
chmod +x VoiceSnip-Linux*.AppImage
./VoiceSnip-Linux*.AppImage
```

### 2. Configure (Optional)

For **Deepgram Cloud** or **Faster Whisper Server**, edit the config file:

- **Windows:** `voicesnip.ini`
- **Linux:** `.env`

```ini
DEEPGRAM_API_KEY=your_api_key_here
DEEPGRAM_ENDPOINT=https://api.deepgram.com/v1/listen

# For Faster Whisper Server:
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

For development or if you prefer running from source:

### Requirements

- Python 3.8+
- Linux: X11 or Wayland (see [Wayland Support](#wayland-support)), Debian/Ubuntu for automated install
- Windows: Python from [python.org](https://www.python.org/downloads/)
- For GPU: NVIDIA GPU with CUDA drivers

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
| **basis** | Whisper CPU + Deepgram Cloud |
| **cuda** | Whisper CPU/GPU + Deepgram Cloud |
| **server** | Faster Whisper Server + Deepgram Cloud |
| **full** | All providers |

Quick install: `./install.py --profile cuda`

### Run

```bash
./start.sh             # Linux
start.bat              # Windows
```

## Provider Comparison

| Provider | Cost | Requirements | Privacy | Best for |
|----------|------|--------------|---------|----------|
| **Whisper Local CPU** | Free | None | Local | Privacy, offline |
| **Whisper Local GPU** | Free | NVIDIA + CUDA | Local | Speed + Privacy |
| **Faster Whisper Server** | Free | Running server | Local/Network | GPU sharing |
| **Deepgram Cloud** | [Pricing](https://deepgram.com/pricing) | API key, Internet | Cloud | Fastest setup |

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
| `.env` | Installation dir | API keys |
| `config.json` | `~/.config/voicesnip/` | GUI settings |
| Whisper models | `~/.cache/huggingface/` | Downloaded models |

## Project Structure

```
voicesnip/
├── main.py              # Entry point
├── install.py           # Installer
├── start.sh / start.bat # Startup scripts
├── voicesnip/           # Main package
│   ├── core.py          # Orchestration
│   ├── audio_recorder.py
│   ├── hotkey_manager.py
│   ├── text_inserter.py
│   └── gui/             # GUI components
└── providers/           # STT providers
    ├── whisper.py
    ├── faster_whisper_server.py
    └── deepgram.py
```

## License

MIT License - see LICENSE file.

**Third-Party:** OpenAI Whisper (MIT), Deepgram API, NVIDIA CUDA

## Author

Stefan Schmidbauer

---

*Developed with AI assistance (Claude/Anthropic)*
