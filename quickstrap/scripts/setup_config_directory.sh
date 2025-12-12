#!/bin/bash
# Post-Install Script Template: Setup Configuration Directory
#
# This script creates configuration directories and default config files.
# Uncomment and modify the sections below to use in your project.

# echo "Setting up configuration directory..."

# Example: Create user config directory
# CONFIG_DIR="$HOME/.config/my-app"
# mkdir -p "$CONFIG_DIR"
# echo "✓ Configuration directory created: $CONFIG_DIR"

# Example: Copy default configuration if it doesn't exist
# DEFAULT_CONFIG="config/default.ini"
# USER_CONFIG="$CONFIG_DIR/config.ini"
#
# if [ ! -f "$USER_CONFIG" ]; then
#     if [ -f "$DEFAULT_CONFIG" ]; then
#         cp "$DEFAULT_CONFIG" "$USER_CONFIG"
#         echo "✓ Default configuration copied to: $USER_CONFIG"
#     else
#         echo "Warning: Default configuration not found: $DEFAULT_CONFIG"
#     fi
# else
#     echo "✓ User configuration already exists: $USER_CONFIG"
# fi

# Example: Create additional directories
# DIRECTORIES=(
#     "$CONFIG_DIR/templates"
#     "$CONFIG_DIR/plugins"
#     "$HOME/.local/share/my-app/data"
#     "$HOME/.cache/my-app"
# )
#
# for dir in "${DIRECTORIES[@]}"; do
#     mkdir -p "$dir"
#     echo "✓ Created: $dir"
# done

# Example: Set proper permissions
# chmod 700 "$CONFIG_DIR"
# echo "✓ Set permissions on config directory"

echo "Configuration setup completed successfully!"
exit 0
