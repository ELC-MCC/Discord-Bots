#!/bin/bash

# Define directories
LOG_FILE="/home/pi/bot_update.log"
REPO_DIR="/home/pi/Discord-Bots"

echo "$(date): Checking for updates..." >> "$LOG_FILE"

if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR" || exit 1

    # Fetch remote changes
    git fetch

    # correct way to check if local is behind remote
    # HEAD..@{u} checks the difference between current branch and its upstream
    if [ $(git rev-list HEAD...@{u} --count) -gt 0 ]; then
        echo "$(date): Updates found! Pulling..." >> "$LOG_FILE"
        git pull >> "$LOG_FILE" 2>&1
        
        # Install potential new requirements
        if [ -d "venv" ]; then
            source venv/bin/activate
            echo "$(date): Updating requirements..." >> "$LOG_FILE"
            pip install -r requirements.txt >> "$LOG_FILE" 2>&1
        fi

        echo "$(date): Restarting Service..." >> "$LOG_FILE"
        sudo systemctl restart discord-bots
        echo "$(date): Update Complete." >> "$LOG_FILE"
    else
        echo "$(date): No updates found." >> "$LOG_FILE"
    fi
else
    echo "$(date): Repository not found at $REPO_DIR" >> "$LOG_FILE"
fi
