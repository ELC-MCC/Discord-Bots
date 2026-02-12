#!/bin/bash

# Setup Script for Main ELC Repo
# This script sets up the bot environment assuming the current repo is the Main ELC one.

echo "============================================="
echo "   ELC Discord Bots Setup (Main Repo)"
echo "============================================="

# 1. Environment Setup
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

# 2. Service Installation
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
