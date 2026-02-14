#!/bin/bash
# Pre-Install Script: Check AMD ROCm Requirements
#
# This script verifies that AMD ROCm drivers are installed and available
# for GPU-accelerated transcription with Whisper.

echo "Checking AMD ROCm requirements..."

# Check if rocm-smi is available
if ! command -v rocm-smi &> /dev/null; then
    echo ""
    echo "✗ Error: ROCm not found (rocm-smi not available)"
    echo ""
    echo "The ROCm profile requires AMD ROCm drivers to be installed."
    echo ""
    echo "Please install ROCm:"
    echo "  1. Follow the official AMD guide:"
    echo "     https://rocm.docs.amd.com/projects/install-on-linux/en/latest/"
    echo ""
    echo "  2. Verify installation with: rocm-smi"
    echo ""
    exit 1
fi

# Run rocm-smi to check if GPU is accessible
if ! rocm-smi &> /dev/null; then
    echo ""
    echo "✗ Error: rocm-smi found but unable to communicate with GPU"
    echo ""
    echo "This may indicate:"
    echo "  - ROCm installation is incomplete"
    echo "  - System needs to be rebooted"
    echo "  - GPU is not properly detected"
    echo "  - User is not in the 'render' or 'video' group"
    echo ""
    echo "Please try:"
    echo "  1. Add your user to the required groups:"
    echo "     sudo usermod -aG render,video \$USER"
    echo "  2. Reboot your system"
    echo "  3. Check with: rocm-smi"
    echo ""
    exit 1
fi

# Display GPU information
echo ""
echo "✓ AMD ROCm detected successfully!"
echo ""
echo "GPU Information:"
rocm-smi --showproductname 2>/dev/null || rocm-smi 2>/dev/null | head -20
echo ""
echo "✓ ROCm requirements check passed!"
echo ""

exit 0
