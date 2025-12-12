#!/bin/bash
# Post-Install Script Template: Check File Exists
#
# This script checks if a required file exists and exits with error if not found.
# Uncomment and modify the sections below to use in your project.

# echo "Checking for required files..."

# Example: Check if a configuration file exists
# CONFIG_FILE="config/settings.json"
# if [ ! -f "$CONFIG_FILE" ]; then
#     echo "Error: Configuration file not found: $CONFIG_FILE"
#     echo "Please create $CONFIG_FILE before running the application."
#     exit 1
# fi
# echo "✓ Configuration file found: $CONFIG_FILE"

# Example: Check if a data directory exists
# DATA_DIR="data"
# if [ ! -d "$DATA_DIR" ]; then
#     echo "Warning: Data directory not found: $DATA_DIR"
#     echo "Creating directory..."
#     mkdir -p "$DATA_DIR"
#     echo "✓ Data directory created: $DATA_DIR"
# else
#     echo "✓ Data directory exists: $DATA_DIR"
# fi

# Example: Check multiple files
# REQUIRED_FILES=(
#     "config/app.ini"
#     "templates/index.html"
#     "static/style.css"
# )
#
# for file in "${REQUIRED_FILES[@]}"; do
#     if [ ! -f "$file" ]; then
#         echo "Error: Required file not found: $file"
#         exit 1
#     fi
#     echo "✓ Found: $file"
# done

echo "File check completed successfully!"
exit 0
