#!/bin/bash
# Post-Install Script: Install pywhispercpp with Vulkan support
#
# The pywhispercpp wheels on PyPI are CPU-only. The Vulkan backend needs a
# source build with GGML_VULKAN=1, which cannot be expressed in a
# requirements.txt file.

PYWHISPERCPP_VERSION="1.5.1"

echo "Building pywhispercpp $PYWHISPERCPP_VERSION with Vulkan support..."
echo "(Compiles whisper.cpp and its Vulkan shaders - this takes a few minutes)"
echo ""

# Detect the virtual environment's pip
if [ -n "$VIRTUAL_ENV" ]; then
    PIP="$VIRTUAL_ENV/bin/pip"
    PYTHON="$VIRTUAL_ENV/bin/python"
else
    # Fallback: look for pip in common venv locations
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
    if [ -f "$PROJECT_DIR/.venv/bin/pip" ]; then
        PIP="$PROJECT_DIR/.venv/bin/pip"
        PYTHON="$PROJECT_DIR/.venv/bin/python"
    else
        PIP="pip3"
        PYTHON="python3"
    fi
fi

echo "Using pip: $PIP"
echo ""

# --no-binary forces the source build; --no-cache-dir keeps pip from reusing
# a previously built CPU-only wheel.
# pywhispercpp's setup.py passes every environment variable to CMake as -D.
# It sets RPATH=$ORIGIN only for editable installs; without it the extension
# points at pip's temporary build dir and fails with "libwhisper.so.1: cannot
# open shared object file" once that dir is gone.
# Remove an existing (possibly CPU-only or broken) build first; pip would
# otherwise consider the requirement satisfied and skip the rebuild.
$PIP uninstall -y pywhispercpp > /dev/null 2>&1

GGML_VULKAN=1 CMAKE_INSTALL_RPATH='$ORIGIN' CMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    $PIP install --no-binary pywhispercpp --no-cache-dir \
    "pywhispercpp==$PYWHISPERCPP_VERSION"

if [ $? -ne 0 ]; then
    echo ""
    echo "✗ Error: Failed to build pywhispercpp with Vulkan"
    echo ""
    echo "Check that the build packages are installed:"
    echo "  sudo apt install build-essential cmake glslc libvulkan-dev spirv-headers"
    echo ""
    echo "Then install it manually:"
    echo "  GGML_VULKAN=1 pip install --no-binary pywhispercpp --no-cache-dir pywhispercpp==$PYWHISPERCPP_VERSION"
    echo ""
    exit 1
fi

# The extension must load its bundled libwhisper/libggml (see RPATH above)
if ! IMPORT_ERROR=$($PYTHON -c "import _pywhispercpp" 2>&1); then
    echo ""
    echo "✗ Error: pywhispercpp was built but cannot be loaded:"
    echo "  $(echo "$IMPORT_ERROR" | tail -1)"
    echo ""
    exit 1
fi

# A build that silently fell back to CPU-only has no Vulkan backend library
PKG_ROOT=$($PYTHON -c "import pathlib, pywhispercpp; print(pathlib.Path(pywhispercpp.__file__).parent.parent)" 2>/dev/null)
if [ -z "$PKG_ROOT" ] || ! find "$PKG_ROOT" -maxdepth 2 -name "libggml-vulkan*.so*" 2>/dev/null | grep -q .; then
    echo ""
    echo "✗ Error: pywhispercpp was installed without the Vulkan backend"
    echo ""
    echo "Check that the build packages are installed and re-run the installer:"
    echo "  sudo apt install build-essential cmake glslc libvulkan-dev spirv-headers"
    echo ""
    exit 1
fi

echo ""
echo "✓ pywhispercpp with Vulkan installed successfully!"
echo ""

exit 0
