#!/bin/bash
# Post-Install Script: Install PyTorch with ROCm support
#
# PyTorch ROCm requires a special index URL and cannot be installed
# via a standard requirements.txt file.

echo "Installing PyTorch with ROCm support..."
echo ""

# Detect the virtual environment's pip
if [ -n "$VIRTUAL_ENV" ]; then
    PIP="$VIRTUAL_ENV/bin/pip"
else
    # Fallback: look for pip in common venv locations
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
    if [ -f "$PROJECT_DIR/.venv/bin/pip" ]; then
        PIP="$PROJECT_DIR/.venv/bin/pip"
    else
        PIP="pip3"
    fi
fi

echo "Using pip: $PIP"
echo ""

# Install PyTorch with ROCm 6.2 support
$PIP install torch torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ PyTorch ROCm installed successfully!"
    echo ""
else
    echo ""
    echo "✗ Error: Failed to install PyTorch ROCm"
    echo ""
    echo "You can install it manually:"
    echo "  pip install torch torchaudio --index-url https://download.pytorch.org/whl/rocm6.2"
    echo ""
    exit 1
fi

exit 0
