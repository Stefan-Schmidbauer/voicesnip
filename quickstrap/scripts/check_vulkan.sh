#!/bin/bash
# Pre-Install Script: Check Vulkan GPU Requirements
#
# This script verifies that a hardware Vulkan device is available for
# GPU-accelerated transcription with whisper.cpp.

echo "Checking Vulkan requirements..."

if ! command -v vulkaninfo &> /dev/null; then
    echo ""
    echo "✗ Error: vulkaninfo not found"
    echo ""
    echo "Please install the Vulkan tools and drivers:"
    echo "  sudo apt install vulkan-tools mesa-vulkan-drivers"
    echo ""
    exit 1
fi

# vulkaninfo tries to create a window surface when a display is set and fails
# without one; the device summary does not need it.
DEVICES=$(env -u DISPLAY -u WAYLAND_DISPLAY vulkaninfo --summary 2>/dev/null \
    | grep "deviceName" | sed 's/.*= //')

# llvmpipe is Mesa's software renderer, not a GPU
GPUS=$(echo "$DEVICES" | grep -v -i "llvmpipe" | grep -v '^$')

if [ -z "$GPUS" ]; then
    echo ""
    echo "✗ Error: No Vulkan GPU found"
    echo ""
    if [ -n "$DEVICES" ]; then
        echo "Only software rendering is available:"
        echo "$DEVICES" | sed 's/^/  - /'
        echo ""
    fi
    echo "This may indicate:"
    echo "  - The GPU's Vulkan driver is missing (AMD/Intel: mesa-vulkan-drivers)"
    echo "  - User is not in the 'render' or 'video' group"
    echo ""
    echo "Please try:"
    echo "  1. Install the driver: sudo apt install mesa-vulkan-drivers"
    echo "  2. Add your user to the required groups:"
    echo "     sudo usermod -aG render,video \$USER"
    echo "  3. Log out and back in, then check with: vulkaninfo --summary"
    echo ""
    exit 1
fi

echo ""
echo "✓ Vulkan GPU detected successfully!"
echo ""
echo "Vulkan GPUs (whisper.cpp numbers them in this order, see VOICESNIP_VULKAN_DEVICE):"
echo "$GPUS" | awk '{ print "  " NR-1 ": " $0 }'
echo ""
echo "✓ Vulkan requirements check passed!"
echo ""

exit 0
