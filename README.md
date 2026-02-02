# Discord Bots 🤖

This repository houses the custom Discord bots for the **Engineering Leadership Council (ELC)**.

## 🌟 Features

### 1. Jeff the Doorman (Welcome Bot)
*   **👋 Smart Greetings**: Welcomes new members with randomized **Engineering Puns** (Electrical, Mechanical & more).
*   **🆔 Auto-Role**: Automatically assigns the "Member" role to anyone who joins (configurable via `.env`).
*   **🧭 Orientation**: Adds a "Where to Start" section linking to key channels (`#general`, `#introductions`, etc.).
*   **🎨 Vibrant visuals**: Uses high-frequency random colors for embeds.
*   **🛡️ Anti-Spam**: Includes a 10-second debounce to prevent duplicate messages if Discord events fire multiple times.

### 2. Sudo Master (Role Manager)
*   **⚡ Reaction Roles**: Create ad-hoc role messages anywhere.
    *   *Usage*: `!setup_reaction #channel "Title" @Role1 @Role2 ...`
    *   *Stateless*: No database required. The bot reads its own message to map emojis to roles.
*   **🔒 Admin Security**: Commands are restricted to users with Administrator permissions.

---

## 🚀 Setup & Installation

### Prerequisites
*   Python 3.8+
*   Discord Bot Token(s) from the [Developer Portal](https://discord.com/developers/applications).
*   **Intents Enabled**: You MUST enable `Presence`, `Server Members`, and `Message Content` intents in the Discord Developer Portal.

### 1. Install Code
```bash
git clone https://github.com/Engineering-Leadership-Council/Discord-Bots.git
cd Discord-Bots
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the root directory:
```ini
# --- Tokens ---
WELCOME_BOT_TOKEN=your_token_here
ROLE_MANAGER_TOKEN=your_role_token_here

# --- Channel IDs ---
WELCOME_CHANNEL_ID=123456789
GENERAL_CHANNEL_ID=123456789
INTRODUCTIONS_CHANNEL_ID=123456789
MAKER_GENERAL_CHANNEL_ID=123456789

# --- Role IDs ---
MEMBER_ROLE_ID=id_to_give_new_users
```

---

## 🛠️ Usage

### Production (Run All Bots)
To run everything at once (e.g., on the Raspberry Pi):
```bash
python main.py
```

### Development (Run Individually)
Test specific bots without interfering with others:
```bash
# Run only Sudo Master
python scripts/run_role_bot.py

# Run only Jeff the Doorman
python scripts/run_welcome_bot.py
```

---

## 🍓 Raspberry Pi Deployment

The user `pi` runs these bots as a systemd service.

### Quick Update
If you've pushed changes to GitHub:
1.  **SSH into the Pi**.
2.  Run the update script (or do it manually):
    ```bash
    cd ~/Discord-Bots
    git pull
    # If requirements changed:
    # source .venv/bin/activate && pip install -r requirements.txt
    sudo systemctl restart discord-bots
    ```

### Logs
Check if the bots are alive:
```bash
journalctl -u discord-bots -f
```
