#!/bin/bash

# Script to start VoiceSnip with Virtual Environment

# Find the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found."
    echo ""
    echo "Please run the installer first:"
    echo "  ./install.py"
    echo ""
    exit 1
fi

# Check if installation config exists
CONFIG_FILE="$HOME/.config/voicesnip/installation_profile.ini"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Installation configuration not found."
    echo ""
    echo "VoiceSnip needs to be installed before use."
    echo "Please run the installer:"
    echo "  ./install.py"
    echo ""
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Set LD_LIBRARY_PATH to include CUDA libraries from venv (only if NVIDIA driver is installed)
# This allows CTranslate2 to find cuDNN and CUBLAS libraries
if command -v nvidia-smi >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    if [ -n "$PYTHON_VERSION" ]; then
        NVIDIA_BASE="venv/lib/python${PYTHON_VERSION}/site-packages/nvidia"
        if [ -d "${NVIDIA_BASE}/cudnn/lib" ] && [ -d "${NVIDIA_BASE}/cublas/lib" ]; then
            export LD_LIBRARY_PATH="${NVIDIA_BASE}/cudnn/lib:${NVIDIA_BASE}/cublas/lib:${LD_LIBRARY_PATH}"
        fi
    fi
fi

# Start VoiceSnip
python3 voicesnip.py "$@"
