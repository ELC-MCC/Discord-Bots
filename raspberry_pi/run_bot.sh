#!/bin/bash

# Navigate to the script's parent directory (the repo root)
# This assumes the script is inside 'raspberry_pi/' and the repo root is one level up
# But for the bootstrap setup, we might place this in the root or handle paths carefully.
# Let's assume the standard structure: /home/pi/Discord-Bots/

REPO_DIR="$(dirname "$(dirname "$(realpath "$0")")")"
cd "$REPO_DIR" || exit 1

# Activate Virtual Environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found! Running with system python3..."
fi

# Run the Bot
# Using exec to replace the shell process with the python process
exec python3 main.py
