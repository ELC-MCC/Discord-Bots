#!/bin/bash

# Setup Script for ELC Discord Bots
# This script guides the user through setting up the bots on a Raspberry Pi.

# Secrets
ELC_ADMIN_CODE="ELC-ADMIN"

echo "============================================="
echo "   ELC Discord Bots Setup Wizard"
echo "============================================="

# 1. Repo Setup
echo ""
echo "Do you want to initialize for the MAIN ELC Repo or a CUSTOM Fork?"
echo "1) Main ELC Repo (Restricted)"
echo "2) Custom Fork (Recommended for other orgs)"
read -p "Select option (1/2): " repo_choice

if [ "$repo_choice" == "1" ]; then
    echo "This option is restricted to official ELC hardware."
    echo "Please insert the ELC Admin USB key now."
    read -p "Press Enter when ready..."

    # Search for the key file in common mount points
    FOUND_KEY="false"
    
    # Check /media/pi (standard Raspberry Pi auto-mount) and /mnt (manual mounts)
    # We use `find` to look for the specific file maxdepth 3 to ignore deep recursions
    echo "Scanning for access key..."
    
    # Arrays of directories to search
    SEARCH_DIRS=("/media" "/mnt" "/run/media")
    
    for dir in "${SEARCH_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            KEY_FILE=$(find "$dir" -maxdepth 3 -name "elc-admin-key.txt" 2>/dev/null | head -n 1)
            if [ ! -z "$KEY_FILE" ]; then
                # Check contents
                CONTENT=$(cat "$KEY_FILE" | tr -d '[:space:]')
                if [ "$CONTENT" == "$ELC_ADMIN_CODE" ]; then
                    FOUND_KEY="true"
                    echo "✅ Key found at: $KEY_FILE"
                    break
                fi
            fi
        fi
    done

    if [ "$FOUND_KEY" == "true" ]; then
        echo "✅ Access Granted. Keeping Main Repo."
    else
        echo "❌ Access Denied. Key file not found or invalid."
        echo "Redirecting to Custom Fork setup..."
        repo_choice="2"
    fi
fi

if [ "$repo_choice" == "2" ]; then
    read -p "Enter your Fork URL (e.g., https://github.com/YourOrg/Discord-Bots.git): " fork_url
    if [ ! -z "$fork_url" ]; then
        echo "Setting origin to $fork_url..."
        git remote set-url origin "$fork_url"
        echo "✅ Origin updated."
    else
        echo "⚠️ No URL provided. Keeping current origin."
    fi
fi

# 2. Environment Setup
echo ""
echo "---------------------------------------------"
echo "Setting up Environment Variables..."
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "✅ .env created."
    read -p "Do you want to edit .env now? (y/n): " edit_env
    if [ "$edit_env" == "y" ]; then
        nano .env
    fi
else
    echo "ℹ️ .env already exists. Skipping creation."
    read -p "Do you want to edit .env? (y/n): " edit_env
    if [ "$edit_env" == "y" ]; then
        nano .env
    fi
fi

# 3. Service Installation
echo ""
echo "---------------------------------------------"
echo "Systemd Service Installation"
read -p "Do you want to install and enable the auto-update service? (y/n): " install_service

if [ "$install_service" == "y" ]; then
    SERVICE_FILE="raspberry_pi/discord-bots.service"
    DEST="/etc/systemd/system/discord-bots.service"
    
    if [ -f "$SERVICE_FILE" ]; then
        echo "Installing service file..."
        # Use sudo for these operations
        sudo cp "$SERVICE_FILE" "$DEST"
        sudo systemctl daemon-reload
        sudo systemctl enable discord-bots
        sudo systemctl start discord-bots
        echo "✅ Service installed and started!"
    else
        echo "❌ Service file not found at $SERVICE_FILE"
    fi
fi

echo ""
echo "============================================="
echo "   Setup Complete!"
echo "============================================="
echo "If you enabled the service, check status with: systemctl status discord-bots"
echo "Otherwise, run manually with: ./scripts/start_and_update.sh"
