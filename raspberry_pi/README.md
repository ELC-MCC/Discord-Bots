# Raspberry Pi Setup Guide

This folder contains everything you need to run these bots on a Raspberry Pi with auto-start and auto-updates.

## 🚀 One-Step Install

1.  Connect to your Raspberry Pi via SSH.
2.  Download the `bootstrap.sh` script:
    ```bash
    wget https://raw.githubusercontent.com/Engineering-Leadership-Council/Discord-Bots/main/raspberry_pi/bootstrap.sh
    ```
3.  Make it executable:
    ```bash
    chmod +x bootstrap.sh
    ```
4.  Run it:
    ```bash
    bash bootstrap.sh
    ```

## 🛠️ What did it do?
-   Installed Python, Git, and Pip.
-   Cloned the repo to `/home/pi/Discord-Bots`.
-   Created a Systemd Service (`discord-bots.service`) so the bot starts on boot.
-   Set up an **Hourly Auto-Update**: Checks GitHub every hour; if new code is found, it pulls it and restarts the bot automatically.

## 🔑 Final Step (Important!)
You must create your `.env` file with your tokens!

```bash
nano /home/pi/Discord-Bots/.env
```

Paste your variables inside:
```ini
WELCOME_BOT_TOKEN=your_token_here
WELCOME_CHANNEL_ID=886081479736709131
GENERAL_CHANNEL_ID=886031679595114528
INTRODUCTIONS_CHANNEL_ID=1412963436102549511
MAKER_GENERAL_CHANNEL_ID=1347068830094069780
```

Save (Ctrl+O, Enter) and Exit (Ctrl+X).

Then restart the service to load the tokens:
```bash
sudo systemctl restart discord-bots
```
