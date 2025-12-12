#!/bin/bash
# Post-Install Script Template: Initialize SQLite Database
#
# This script initializes a SQLite database if it doesn't exist.
# Uncomment and modify the sections below to use in your project.

# echo "Checking SQLite database..."

# Example: Initialize database if it doesn't exist
# DB_FILE="data/app.db"
# SCHEMA_FILE="schema.sql"
#
# # Create data directory if needed
# mkdir -p "$(dirname "$DB_FILE")"
#
# if [ ! -f "$DB_FILE" ]; then
#     echo "Database not found. Initializing..."
#
#     # Option 1: Initialize from SQL schema file
#     if [ -f "$SCHEMA_FILE" ]; then
#         sqlite3 "$DB_FILE" < "$SCHEMA_FILE"
#         if [ $? -eq 0 ]; then
#             echo "✓ Database initialized from schema: $SCHEMA_FILE"
#         else
#             echo "Error: Failed to initialize database from schema"
#             exit 1
#         fi
#     else
#         # Option 2: Initialize using Python script
#         if [ -f "scripts/init_db.py" ]; then
#             python3 scripts/init_db.py
#             if [ $? -eq 0 ]; then
#                 echo "✓ Database initialized using Python script"
#             else
#                 echo "Error: Failed to initialize database"
#                 exit 1
#             fi
#         else
#             echo "Error: No schema file or init script found"
#             exit 1
#         fi
#     fi
# else
#     echo "✓ Database already exists: $DB_FILE"
# fi

# Example: Verify database structure
# TABLE_COUNT=$(sqlite3 "$DB_FILE" "SELECT count(*) FROM sqlite_master WHERE type='table';")
# echo "✓ Database contains $TABLE_COUNT tables"

echo "Database check completed successfully!"
exit 0
