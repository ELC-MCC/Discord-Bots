# 🤖 ELC Discord Bots

**Professional Automation for the Engineering Leadership Council**

This repository hosts a suite of custom-built Discord bots designed to automate community management, streamline event scheduling, and enhance member onboarding. Built with `discord.py`, these services are optimized for reliability and ease of use on Raspberry Pi and Linux environments.

---

## ✨ Features & Bot Modules

### 1. 📅 The Event Loop (Event Bot)
**Status:** `Active` | **Prefix:** `!`

A comprehensive event management system that keeps the community informed.

#### **Key Features:**
*   **Live Dashboard:** A persistent, auto-updating message that always displays the next 3 upcoming events.
*   **Smart Scheduling:** Interactive forms for adding events with image support.
*   **Automated Reminders:** Posts "Event Starting" announcements automatically.
*   **Clean UI:** Uses ephemeral (private) menus and buttons to keep chat channels clutter-free.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!add_event` | Public | Sends a button to open the **Add Event** form (Name, Date, Time, Loc, Desc, Image). |
| `!delete_event` | Public | Sends a button to open a private menu for deleting events. |
| `!list_events` | Public | Displays a list of ALL currently scheduled events. |
| `!upcoming` | Public | Shows the next 3 scheduled events in chat. |
| `!setup_upcoming` | **Admin** | Creates the **Live Dashboard** message in the current channel. |

---

### 2. 🛡️ Sudo Master (Role Bot)
**Status:** `Active` | **Prefix:** `!`

Manages role assignments, self-service roles, and bulk migrations.

#### **Key Features:**
*   **Reaction Roles:** Allows users to assign themselves roles by reacting to a message.
*   **Auto-Join Role:** Automatically assigns a baseline role (e.g., "Member") to new users.
*   **Legacy Fixer:** Tools to migrate roles based on member join dates.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!setup_reaction` | **Admin** | Creates a reaction role message.<br>**Usage:** `!setup_reaction #channel "Title" <Emoji> @Role` |
| `!fix_roles` | **Admin** | **Advanced:** Migrates users from one role to another based on join date.<br>**Usage:** `!fix_roles @OldRole @Pre2024Role @Post2024Role` |

---

### 3. 👋 Jeff the Doorman (Welcome Bot)
**Status:** `Active` | **Trigger:** `on_member_join`

Ensures every new member receives a warm welcome and direction.

#### **Key Features:**
*   **Engineering Puns:** Selects from a curated list of engineering-themed welcome messages.
*   **Dynamic Orientation:** Directs users to key channels based on server configuration.
*   **Auto-Role:** Assigns the initial "Member" role immediately upon joining.

---

## 🚀 Installation & Setup

These bots are designed to run as a **Systemd Service** on a Raspberry Pi or Ubuntu server, ensuring they start on boot and restart automatically if they crash.

### Prerequisites
*   Python 3.8+
*   Git
*   A Discord Bot Token (from the [Discord Developer Portal](https://discord.com/developers/applications))

### 1. Clone the Repository
```bash
git clone https://github.com/Engineering-Leadership-Council/Discord-Bots.git
cd Discord-Bots
```

### 2. Run the Setup Script
We provide interactive scripts that handle dependency installation, `.env` creation, and service setup.

**Make scripts executable:**
```bash
chmod +x scripts/setup_main.sh scripts/setup_fork.sh
```

**Choose your setup mode:**

| Option | Command | Use Case |
| :--- | :--- | :--- |
| **Standard** | `./scripts/setup_main.sh` | For the main ELC Server deployment. |
| **Fork/Custom** | `./scripts/setup_fork.sh` | For devs or other orgs using a fork. |

**The script will:**
1.  Install Python requirements from `requirements.txt`.
2.  Help you configure the `.env` file with your tokens.
3.  Install and start the `discord-bots` systemd service.

---

## ⚙️ Configuration

### Environment Variables (`.env`)
The bot relies on a `.env` file for secrets and channel IDs.
*(See `.env.example` for the full template)*

```ini
# Tokens
DISCORD_TOKEN=your_token_here

# Channel IDs (Enable Developer Mode in Discord to copy IDs)
EVENT_CHANNEL_ID=123456789
WELCOME_CHANNEL_ID=123456789
GENERAL_CHANNEL_ID=123456789
INTRODUCTIONS_CHANNEL_ID=123456789
MAKER_GENERAL_CHANNEL_ID=123456789

# Role IDs
MEMBER_ROLE_ID=123456789
AUTO_JOIN_ROLE_ID=123456789
```

### Feature Toggles (`bot_config.py`)
You can easily enable or disable specific bots by editing `bot_config.py`:

```python
ENABLE_ROLE_BOT = True
ENABLE_WELCOME_BOT = True
ENABLE_EVENT_BOT = True

# Branding
ROLE_BOT_NICKNAME = "Sudo Master"
EVENT_BOT_NICKNAME = "The Event Loop"
```

---

## 🔄 Management & Updates

### Auto-Update System
The service is configured to **automatically pull the latest code** from GitHub every time it restarts. To update the bots, simply push to the `main` branch and then restart the service on the Pi.

### Service Commands
Control the bot service using standard systemctl commands:

```bash
# Check Status
sudo systemctl status discord-bots

# Restart (Triggers Update)
sudo systemctl restart discord-bots

# Stop
sudo systemctl stop discord-bots

# View Logs
journalctl -u discord-bots -f
```

---

**Developed for the Engineering Leadership Council**
