#!/bin/bash

# Setup Script for ELC Discord Bots
# This script guides the user through setting up the bots on a Raspberry Pi.

if [ "$repo_choice" == "1" ]; then
    echo "✅ Selected Main ELC Repo."
    # No action needed, origin remains as checked out
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
