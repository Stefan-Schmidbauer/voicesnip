#!/bin/bash
# Post-Install Script: Check NVIDIA CUDA Requirements
#
# This script verifies that NVIDIA drivers are installed and CUDA is available
# for GPU-accelerated transcription with Whisper.

echo "Checking NVIDIA GPU and CUDA requirements..."

# Check if nvidia-smi is available
if ! command -v nvidia-smi &> /dev/null; then
    echo ""
    echo "✗ Error: NVIDIA driver not found (nvidia-smi not available)"
    echo ""
    echo "The CUDA profile requires NVIDIA GPU drivers to be installed."
    echo ""
    echo "Please install NVIDIA drivers:"
    echo "  1. Check available driver versions:"
    echo "     apt search nvidia-driver"
    echo ""
    echo "  2. Install a suitable driver (replace XXX with version number):"
    echo "     sudo apt install nvidia-driver-XXX"
    echo ""
    echo "  3. Reboot your system after installation"
    echo ""
    echo "  4. Verify installation with: nvidia-smi"
    echo ""
    exit 1
fi

# Run nvidia-smi to check if GPU is accessible
if ! nvidia-smi &> /dev/null; then
    echo ""
    echo "✗ Error: nvidia-smi found but unable to communicate with GPU"
    echo ""
    echo "This may indicate:"
    echo "  - Driver installation is incomplete"
    echo "  - System needs to be rebooted"
    echo "  - GPU is not properly detected"
    echo ""
    echo "Please try:"
    echo "  1. Reboot your system"
    echo "  2. Check dmesg for NVIDIA driver messages: dmesg | grep -i nvidia"
    echo "  3. Reinstall NVIDIA drivers if necessary"
    echo ""
    exit 1
fi

# Display GPU information
echo ""
echo "✓ NVIDIA driver detected successfully!"
echo ""
echo "GPU Information:"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | while IFS=, read -r name driver memory; do
    echo "  GPU Model:      $name"
    echo "  Driver Version: $driver"
    echo "  GPU Memory:     $memory"
done

echo ""
echo "✓ CUDA requirements check passed!"
echo ""

exit 0
