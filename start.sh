#!/bin/bash

# Quickstrap - Generic Application Starter
# Reads configuration from quickstrap/installation_profiles.ini

# Function to read INI file values
read_ini_value() {
    local file="$1"
    local section="$2"
    local key="$3"

    # Use awk to parse INI file (handles values containing '=' signs)
    awk -v section="[$section]" -v key="$key" '
        $0 == section { in_section=1; next }
        /^\[/ { in_section=0 }
        in_section && match($0, "^[[:space:]]*"key"[[:space:]]*=") {
            val = substr($0, RSTART + RLENGTH)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
            print val
            exit
        }
    ' "$file"
}

# Find the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Parse quickstrap/installation_profiles.ini
APP_NAME=$(read_ini_value "quickstrap/installation_profiles.ini" "metadata" "app_name")

# Try platform-specific start_command first, then fall back to generic
START_CMD=$(read_ini_value "quickstrap/installation_profiles.ini" "metadata" "start_command_linux")
if [ -z "$START_CMD" ]; then
    START_CMD=$(read_ini_value "quickstrap/installation_profiles.ini" "metadata" "start_command")
fi

# Fallback defaults
APP_NAME=${APP_NAME:-"Application"}
START_CMD=${START_CMD:-"python main.py"}

# Validate start command
if [ -z "$START_CMD" ]; then
    echo "Error: No start command configured in installation_profiles.ini"
    exit 1
fi

# App name lowercase for config filename (normalize: spaces and slashes to underscores)
APP_NAME_LOWER=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]' | tr ' /' '__')

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found for $APP_NAME."
    echo ""
    echo "Please run the installer first:"
    echo "  ./install.py"
    echo ""
    exit 1
fi

# Check if installation config exists (in project directory)
CONFIG_FILE="./${APP_NAME_LOWER}_profile.ini"
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
source venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Convert python3 to python (venv always provides 'python' on all platforms)
if [ "$START_CMD" = "python3" ]; then
    START_CMD="python"
else
    START_CMD=${START_CMD//python3 /python }
fi

# Start application with all provided arguments
echo "Starting $APP_NAME..."
read -ra CMD_ARRAY <<< "$START_CMD"
"${CMD_ARRAY[@]}" "$@"
