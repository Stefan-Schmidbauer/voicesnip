#!/bin/bash
# Post-Install Script: Setup CUDA Environment in venv/bin/activate
#
# This script modifies venv/bin/activate to set LD_LIBRARY_PATH for cuDNN/cuBLAS libraries
# Required for GPU-accelerated Whisper transcription with CTranslate2

echo "Configuring CUDA environment in venv/bin/activate..."

# Check if nvidia-smi is available (CUDA support present)
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "✓ nvidia-smi not found - skipping CUDA environment setup"
    exit 0
fi

# Detect Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
if [ -z "$PYTHON_VERSION" ]; then
    echo "✗ Error: Could not detect Python version"
    exit 1
fi

# Find venv/bin/activate relative to VIRTUAL_ENV
ACTIVATE_FILE="$VIRTUAL_ENV/bin/activate"

if [ ! -f "$ACTIVATE_FILE" ]; then
    echo "✗ Error: venv/bin/activate not found at $ACTIVATE_FILE"
    exit 1
fi

# Check if CUDA libraries exist in venv
NVIDIA_BASE="$VIRTUAL_ENV/lib/python${PYTHON_VERSION}/site-packages/nvidia"
if [ ! -d "${NVIDIA_BASE}/cudnn/lib" ] || [ ! -d "${NVIDIA_BASE}/cublas/lib" ]; then
    echo "✓ CUDA libraries not found in venv - skipping CUDA environment setup"
    exit 0
fi

# Check if already configured (avoid duplicate modifications)
if grep -q "LD_LIBRARY_PATH.*nvidia.*cudnn" "$ACTIVATE_FILE"; then
    echo "✓ CUDA environment already configured in venv/bin/activate"
    exit 0
fi

# Append LD_LIBRARY_PATH export to venv/bin/activate
cat >> "$ACTIVATE_FILE" << EOF

# CUDA Library Path (added by VoiceSnip installer)
# Set LD_LIBRARY_PATH to include CUDA libraries for CTranslate2/Faster-Whisper
export LD_LIBRARY_PATH="${NVIDIA_BASE}/cudnn/lib:${NVIDIA_BASE}/cublas/lib:\${LD_LIBRARY_PATH}"
EOF

echo "✓ CUDA environment configured in venv/bin/activate"
echo ""
echo "LD_LIBRARY_PATH will be automatically set when activating the virtual environment"
echo ""

exit 0
