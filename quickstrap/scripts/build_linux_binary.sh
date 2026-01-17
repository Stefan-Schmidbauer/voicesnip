#!/bin/bash
#
# Build Linux Binary using PyInstaller
#
# This script creates a standalone Linux executable from your Python application.
# The resulting binary can be distributed to Linux users without requiring Python installation.
#
# Usage:
#   ./quickstrap/scripts/build_linux_binary.sh
#
# Requirements:
#   - PyInstaller must be installed in your virtual environment
#   - Run this after installing your application with ./install.py
#
# Output:
#   - Binary file will be in dist/ directory
#   - Build artifacts in build/ directory
#
# Environment Variables (optional):
#   QUICKSTRAP_APP_NAME    - Application name (from metadata)
#   QUICKSTRAP_CONFIG_DIR  - Config directory (from metadata)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Linux Binary Build Script${NC}"
echo -e "${BLUE}======================================${NC}"
echo

# Check if we're on Linux
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo -e "${YELLOW}⚠ Warning: You are running this on Windows${NC}"
    echo
    echo "PyInstaller builds for the current platform only."
    echo "This will create a Windows binary, NOT a Linux binary."
    echo
    echo "To create a Linux binary:"
    echo "  1. Run this script on Linux"
    echo
    echo "To create a Windows EXE:"
    echo "  1. Run on Windows: .\\quickstrap\\scripts\\build_windows_exe.ps1"
    echo
    read -p "Continue anyway? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Build cancelled."
        exit 0
    fi
    echo
fi

# Find the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Error: Virtual environment not found${NC}"
    echo
    echo "Please run the installer first:"
    echo "  ./install.py"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if PyInstaller is installed
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo -e "${YELLOW}⚠ PyInstaller not found in virtual environment${NC}"
    echo
    echo "Installing PyInstaller..."
    pip install pyinstaller
    echo
fi

# Read configuration from installation_profiles.ini
CONFIG_FILE="quickstrap/installation_profiles.ini"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}✗ Error: Configuration file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Parse INI file (simple parser)
APP_NAME=$(python -c "
from configparser import ConfigParser
config = ConfigParser()
config.read('$CONFIG_FILE')
print(config.get('metadata', 'app_name', fallback='Application'))
" 2>/dev/null || echo "Application")

START_COMMAND=$(python -c "
from configparser import ConfigParser
config = ConfigParser()
config.read('$CONFIG_FILE')
print(config.get('metadata', 'start_command', fallback='python3 main.py'))
" 2>/dev/null || echo "python3 main.py")

# Extract main script from start_command
# Remove 'python3 ' or 'python ' prefix
MAIN_SCRIPT=$(echo "$START_COMMAND" | sed -e 's/^python3 //' -e 's/^python //' | awk '{print $1}')

if [ ! -f "$MAIN_SCRIPT" ]; then
    echo -e "${RED}✗ Error: Main script not found: $MAIN_SCRIPT${NC}"
    echo
    echo "Please verify the 'start_command' in $CONFIG_FILE"
    echo "Current start_command: $START_COMMAND"
    exit 1
fi

echo -e "${GREEN}✓ Configuration loaded${NC}"
echo "  Application: $APP_NAME"
echo "  Main script: $MAIN_SCRIPT"
echo

# Check for PyInstaller spec file
SPEC_FILE="quickstrap/pyinstaller.spec"

if [ -f "$SPEC_FILE" ]; then
    echo -e "${BLUE}ℹ Using existing PyInstaller spec file: $SPEC_FILE${NC}"
    echo

    # Build using spec file
    echo "Building binary with custom configuration..."
    pyinstaller --clean --noconfirm "$SPEC_FILE"
else
    echo -e "${BLUE}ℹ No spec file found, using automatic build${NC}"
    echo

    # Auto-detect common patterns for additional data
    ADD_DATA_ARGS=""

    # Check for common directories that should be included
    for dir in config templates static data resources; do
        if [ -d "$dir" ]; then
            echo -e "${GREEN}✓ Found directory: $dir (will be included)${NC}"
            ADD_DATA_ARGS="$ADD_DATA_ARGS --add-data $dir:$dir"
        fi
    done

    # Check for icon file
    ICON_ARG=""
    for icon in app.ico icon.ico application.ico; do
        if [ -f "$icon" ]; then
            echo -e "${GREEN}✓ Found icon: $icon${NC}"
            ICON_ARG="--icon=$icon"
            break
        fi
    done

    echo
    echo "Building Linux binary..."

    # Build command
    pyinstaller \
        --onefile \
        --name "$APP_NAME" \
        $ICON_ARG \
        $ADD_DATA_ARGS \
        "$MAIN_SCRIPT"
fi

# Check if build was successful
if [ -f "dist/$APP_NAME" ] || [ -f "dist/$(basename $MAIN_SCRIPT .py)" ]; then
    echo
    echo -e "${BLUE}======================================${NC}"
    echo -e "${GREEN}✓ Build successful!${NC}"
    echo -e "${BLUE}======================================${NC}"
    echo
    echo "Build output: dist/"
    echo
    ls -lh dist/
    echo
    echo "You can now distribute the binary to Linux users."
    echo "No Python installation required on their systems."
    echo
    echo "Note: The binary is platform-specific. For other platforms:"
    echo "  - Windows: Run .\\quickstrap\\scripts\\build_windows_exe.ps1"
else
    echo
    echo -e "${RED}✗ Build failed${NC}"
    echo
    echo "Check the output above for errors."
    exit 1
fi
