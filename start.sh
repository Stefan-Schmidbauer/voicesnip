#!/bin/bash

# Quickstrap - Generic Application Starter
# Reads configuration from quickstrap/installation_profiles.ini

# Function to read INI file values
read_ini_value() {
    local file="$1"
    local section="$2"
    local key="$3"

    # Use awk to parse INI file
    awk -F '=' -v section="[$section]" -v key="$key" '
        $0 == section { in_section=1; next }
        /^\[/ { in_section=0 }
        in_section && $1 ~ "^[[:space:]]*"key"[[:space:]]*$" {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
            print $2
            exit
        }
    ' "$file"
}

# Find the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse quickstrap/installation_profiles.ini
APP_NAME=$(read_ini_value "quickstrap/installation_profiles.ini" "metadata" "app_name")
CONFIG_DIR=$(read_ini_value "quickstrap/installation_profiles.ini" "metadata" "config_dir")
START_CMD=$(read_ini_value "quickstrap/installation_profiles.ini" "metadata" "start_command")

# Fallback defaults
APP_NAME=${APP_NAME:-"Application"}
CONFIG_DIR=${CONFIG_DIR:-"app"}
START_CMD=${START_CMD:-"python3 main.py"}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found for $APP_NAME."
    echo ""
    echo "Please run the installer first:"
    echo "  ./install.py"
    echo ""
    exit 1
fi

# Check if installation config exists
CONFIG_FILE="$HOME/.config/$CONFIG_DIR/installation_profile.ini"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Installation configuration not found."
    echo ""
    echo "$APP_NAME needs to be installed before use."
    echo "Please run the installer:"
    echo "  ./install.py"
    echo ""
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Start application
echo "Starting $APP_NAME..."
eval "$START_CMD"
