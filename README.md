# Discord Bots

This repository contains the custom Discord bots developed for the **Engineering Leadership Council (ELC)**. These services are designed to automate server management, onboard new members, and schedule organization events.

## Features

### 1. Jeff the Doorman (Welcome Bot)
*   **Smart Greetings**: Welcomes new members with randomized engineering-themed messages.
*   **Auto-Role**: Automatically assigns the "Member" role to new users.
*   **Orientation**: Provides a "Where to Start" section with links to key channels.

### 2. Sudo Master (Role Manager)
*   **Reaction Roles**: Facilitates ad-hoc role assignment via reaction monitoring.
    *   *Usage*: `!setup_reaction #channel "Title" <Emoji> @Role ...`
    *   *Example*: `!setup_reaction #roles "Select your team" 🔴 @RedTeam 🔵 @BlueTeam`
    *   *Supports*: Unicode Emojis (🔴) and Custom Discord Emojis (`<:pepe:123>`).
*   **Access Control**: Critical commands are restricted to Administrators.

### 3. The Event Loop (Event & Dashboard Bot)
*   **Event Scheduling**: Schedule events with `!add_event`.
    *   *Usage*: `!add_event "Name" "YYYY-MM-DD" "HH:MM" "Description" [ImageURL]`
    *   *Example*: `!add_event "Pizza Party" "2024-12-25" "18:00" "Join us for food and games!"`
*   **Managing Events**:
    *   *List Events*: `!list_events` - Shows all upcoming events with their ID numbers.
    *   *Delete Event*: `!delete_event <ID>`
    *   *Example*: `!delete_event 1`
*   **Persistent Dashboard**: Keeps a pinned message in a channel up-to-date with all upcoming events.
    *   *Setup*: `!setup_dashboard #channel`
    *   *Auto-Update*: Updates automatically when events are added, deleted, or expire.
*   **Automated Notifications**: Posts announcements when events start.

---

## Configuration

### 1. Bot Toggles (`bot_config.py`)
You can enable/disable specific bots without changing code. Edit `bot_config.py` in the root directory:
```python
ENABLE_ROLE_BOT = True
ENABLE_WELCOME_BOT = True
ENABLE_EVENT_BOT = True
```

### 2. Branding (`bot_config.py`)
Customize bot nicknames and footer text in `bot_config.py` to match your organization's branding.

### 3. Environment Variables (`.env`)
The setup scripts will help you generate this file from `.env.example`.

---

## Setup and Installation

We provide interactive scripts to set up the bots on a Raspberry Pi (or any Linux environment).

### 1. Clone the Repository
```bash
git clone https://github.com/Engineering-Leadership-Council/Discord-Bots.git
cd Discord-Bots
```

### 2. Run the Setup Script
Make the scripts executable:
```bash
chmod +x scripts/setup_main.sh scripts/setup_fork.sh
```

**Option A: Main ELC Repo** (Default)
```bash
./scripts/setup_main.sh
```

**Option B: Custom Fork** (For other organizations)
```bash
./scripts/setup_fork.sh
```

**These scripts will:**
1.  Verify/Install Python dependencies (`requirements.txt`).
2.  Help you create and edit your `.env` file.
3.  **Install the Systemd Service** for auto-updates (optional but recommended).

### 3. Auto-Update Service
If you installed the service, the bot will:
-   Start automatically on boot.
-   **Pull the latest code** from GitHub every time it restarts.
-   Restart automatically if it crashes.

To manage the service manually:
```bash
sudo systemctl status discord-bots
sudo systemctl restart discord-bots
sudo systemctl stop discord-bots
```
