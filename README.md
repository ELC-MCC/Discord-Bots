# ELC Discord Bots

**Professional Automation for the Engineering Leadership Council**

This repository hosts a suite of custom-built Discord bots designed to automate community management, streamline event scheduling, and enhance member onboarding. Built with `discord.py`, these services are optimized for reliability and ease of use on Raspberry Pi and Linux environments.

---

## Features & Bot Modules

### 1. The Event Loop (Event Bot)
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
| `!add_event` | **Admin** | Sends a button to open the **Add Event** form (Name, Date, Time, Loc, Desc, Image). |
| `!delete_event` | **Admin** | Sends a button to open a private menu for deleting events. |
| `!list_events` | Public | Displays a list of ALL currently scheduled events. |
| `!upcoming` | Public | Shows the next 3 scheduled events in chat. |
| `!setup_upcoming` | **Admin** | **UI Available:** Use the button in `!admin_setup` to place the dashboard. |

---

### 2. Sudo Master (Role Bot)
**Status:** `Active` | **Prefix:** `!`

Manages role assignments, self-service roles, and bulk migrations.

#### **Key Features:**
*   **Reaction Roles:** Allows users to assign themselves roles by reacting to a message.
*   **Auto-Join Role:** Automatically assigns a baseline role (e.g., "Member") to new users.
*   **Legacy Fixer:** Tools to migrate roles based on member join dates.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!setup_reaction` | **Admin** | **UI Available:** Use `!admin_setup` -> "Setup Reaction Roles" to create menus interactively.<br>Manual: `!setup_reaction #channel "Title" <Emoji> @Role` |
| `!migrate_alumni` | **Admin** | **Alumni Migration:** Assigns Alumni/Member roles based on join date.\n**UI Available:** Use `!admin_setup` -> "Migrate Roles".

---

### 3. Jeff the Doorman (Welcome Bot)
**Status:** `Active` | **Trigger:** `on_member_join`

Ensures every new member receives a warm welcome and direction.

#### **Key Features:**
*   **Engineering Puns:** Selects from a curated list of engineering-themed welcome messages.
*   **Dynamic Orientation:** Lists only the channels that are actually configured, so an unset ID never renders a broken mention.
*   **Deferred Welcomes:** Waits for Membership Screening to finish before greeting, when the server uses it.
*   **Self-Diagnosis:** Reports at startup, and on demand, whether welcomes can actually be delivered, instead of failing silently.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!welcome_check` | **Admin** | Checks the welcome channel, its permissions and the required intents, then states exactly what is wrong. |
| `!admin_setup` | **Admin** | Posts this bot's control panel into the admin channel. |

**This bot does not assign roles.** Auto-role on join is handled by Sudo Master (Role Bot) through `AUTO_JOIN_ROLE_ID`, falling back to `MEMBER_ROLE_ID`.

#### **If welcomes are not appearing:**
1.  Confirm the bot is actually running. On startup it logs either `[startup] Welcome Bot: SKIPPED. WELCOME_BOT_TOKEN is empty or missing in .env` or a `WelcomeBot: ready in <server>` line. A blank token means this bot never starts while the others keep working.
2.  Run `!welcome_check` in the server and read the problems it lists.
3.  In the [Discord Developer Portal](https://discord.com/developers/applications), open this bot's application, go to **Bot > Privileged Gateway Intents**, and enable **Server Members** and **Message Content**.
4.  Confirm the bot has **View Channel**, **Send Messages** and **Embed Links** in the welcome channel. Category permission changes cascade into the channel, so check the parent category too.

When a welcome is blocked by permissions, the bot posts a one-time notice in `ADMIN_CHANNEL_ID` (if set) so a permission change cannot go unnoticed, and every blocked attempt is logged with a `WelcomeBot problem:` prefix that can be grepped out of the Stream Bot noise. Welcomes are retried on the next event once the permission is restored.

---

### 4. The G-Code Guardian (Stream Bot)
**Status:** `Active` | **Prefix:** `None`

Streams MJPEG video from local network sources to a Discord channel. Supports multiple concurrent streams with automatic recovery and status indicators.

#### **Key Features:**
*   **Multi-Stream Support:** Configure up to 5 streams via `.env`.
*   **Printer Status Integration:** Automatically fetches and displays real-time 3D printer status:
    *   **Supports:** Moonraker/Klipper (Standard) & **Elegoo SDCP** (Centauri Carbon).
    *   **Displays:** Filename, Print Progress (%), Elapsed Time, and Estimated Time Left.
    *   **Idle State:** Shows clean placeholders (`--`) when the printer is not active.
*   **Smart Recovery:** Automatically attempts to reconnect if a stream goes offline (e.g., printer power cycle).
*   **Wake-on-Connect:** Mimics a browser connection to force "lazy" cameras to start streaming immediately.
*   **Persistence:** Reuses existing stream messages on restart to prevent channel clutter.

#### **Configuration (.env):**
1.  Add `STREAM_BOT_TOKEN`.
2.  Set `STREAM_CHANNEL_ID` to the channel where streams should appear.
3.  Configure streams using the pattern `STREAM_X_...` and optional `PRINTER_X_...`:

```ini
STREAM_BOT_TOKEN=...
STREAM_CHANNEL_ID=123456789 (Developer Mode -> Copy ID)

# --- Printer 1 (Standard Klipper) ---
STREAM_1_URL=http://192.168.1.101:8080/video
STREAM_1_TITLE=Bambu Lab X1C
# Optional: Explicitly set printer API URL (defaults to http://<stream_ip>:7125)
PRINTER_1_URL=http://192.168.1.101:7125

# --- Printer 2 (Elegoo / SDCP) ---
STREAM_2_URL=http://192.168.1.102:8080/stream
STREAM_2_TITLE=Elegoo Centauri
# SDCP uses port 3030 over WebSocket
PRINTER_2_URL=ws://192.168.1.102:3030/websocket
```

#### **Commands:**
*   `!restart_streams` - **Admin Only** - **Purges the last 100 messages** in the stream channel and forces a clean restart of all stream tasks. Use this if streams get stuck or de-synced.



---

### 5. The Timekeeper (Schedule Bot)
**Status:** `Active` | **Prefix:** `!`

Manages and displays the weekly schedule for the Makerspace or community events.

#### **Key Features:**
*   **Weekly Schedule Display:** A pinned, auto-updating embed showing open hours for each day of the week.
*   **Interactive Editing:** Admins can update the schedule using a simple modal form in Discord, no code changes required.
*   **Smart Formatting:** Automatically formats days and times for readability.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!set_schedule_channel` | **Admin** | **UI Available:** Use `!admin_setup` -> "Set Display Channel". |
| `!setup_schedule` | **Admin** | Spawns the "Edit Weekly Schedule" button for admins to update times. |

---

### 6. Filament Tracker (Filament Bot)
**Status:** `Active` | **Prefix:** `!`

Manages 3D printer filament inventory, tracking usage and remaining weights.

#### **Key Features:**
*   **Dual Dashboards:** Separate interfaces for public usage (logging) and admin management (adding/editing).
*   **Consumption Stats:** Live tracking of Daily, Weekly, and Monthly filament usage.
*   **Log Export:** Admins can export log history to CSV directly from Discord (Admin Dashboard).
*   **Data Compatibility:** Uses the same JSON database structure as the ELC Filament Tracker desktop app.
*   **Project Pools:** Filament can be allocated to a named project (see below) while staying in the main inventory.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!filament setup` | **Admin** | Deploys the Public and Admin dashboards to the channels specified in `.env`. |
| `!project setup <key>` | **Admin** | Deploys a project's dashboard and pool controls to that project's channel. `!wheelchair setup` is an alias for the default project. |

#### **Project: 3D Printed Wheelchair**

A project pool is a tag on the main inventory, not a second inventory. A spool allocated to a project is still an ordinary main-pool spool, so it appears in the main dashboard and the main log picker as well as in the project tracker. Usage logged against a project is written to the same log file, so it is counted in the main Daily/Weekly/Monthly/Total stats as well as in a project-only subtotal.

*   **Adding filament:** the main admin panel's `Add Filament` button first asks which pool the spool belongs to (main pool only, or any registered project), so project spools can be created from the admin panel.
*   **Logging is PIN gated.** `PROJECT_WHEELCHAIR_PIN` lives in `.env` on the server only. It is never posted, never embedded, and never echoed back. The filament picker only appears after the PIN checks out, and every reply on that path is ephemeral, so nothing about the flow is visible to anyone else in the server. Each project has its own PIN.
*   **The project channel carries only the `Log Project Usage` button.** Pool management is not posted there; it is reached from the main admin panel's `Project Pools` button, which is admin only and replies privately. From there you can register a new spool straight into a pool, allocate an existing spool, unallocate one (which leaves it in the main inventory), or export that project's usage log.
*   `PROJECT_WHEELCHAIR_CHANNEL_ID` and `PROJECT_WHEELCHAIR_PIN` must be added to `.env` by hand on the server, since `.env` is not version controlled.

#### **Adding Another Project**

Add one entry to the `PROJECTS` dict in `bots/filament_bot.py`, then add the matching env vars on the server:

```python
PROJECTS = {
    "wheelchair": "3D Printed Wheelchair",
    "gokart": "ELC Go-Kart",          # <- new
}
```

```
PROJECT_GOKART_CHANNEL_ID=
PROJECT_GOKART_PIN=
```

Then run `!project setup gokart` in that project's channel. The env var names, the pool pickers, the dashboards, the PIN gate and the button IDs are all derived from the project key, so no other code changes are needed. `!project setup` posts that project's dashboard only; pool management for every project is reached from the main admin panel.

---

### 7. Megaphone Man (Announcement Bot)
**Status:** `Active` | **Prefix:** `!`

Writes and schedules server announcements from a button in the admin panel, so nothing has to be posted by hand at the right moment.

#### **Key Features:**
*   **Compose From A Button:** Asks for a title, a send time, then the announcement text. All three in one form.
*   **Timed Delivery:** Announcements are queued and posted automatically, even if the bot was offline when the time arrived.
*   **Flexible Times:** Accepts `30m`, `2h`, `1h30m`, `3 days`, `tomorrow 8:00`, `2026-09-14 19:30`, `09/14/2026 7:30 PM`, or `now`.
*   **Confirm Step:** Shows a private preview of the parsed send time before anything is queued, so a typo never turns into a mis-timed post.
*   **Set The Target Channel:** The admin panel picks which channel announcements are posted to, with a permission check on the chosen channel.
*   **Optional @everyone:** Schedule a post with or without a ping.
*   **Manageable Queue:** Review, send early, or cancel anything that is still waiting.
*   **History:** See what already went out, when, and whether it failed.

#### **Command Reference:**
| Command | Permission | Description |
| :--- | :--- | :--- |
| `!admin_setup` | **Admin** | Posts this bot's control panel into the admin channel. |
| `!announce` | **Admin** | Sends a button that opens the compose form. |
| `!announce list` | **Admin** | Lists everything still queued, with IDs. |
| `!announce cancel <id>` | **Admin** | Cancels a queued announcement. |
| `!announce channel` | **Admin** | Sets the target channel to the current channel. |

#### **Scheduling Notes:**
Times are anchored to `America/New_York` by default, so `2026-09-14 19:30` means 7:30 PM Eastern even when the server clock is set to UTC (the usual state of a fresh box). Override with `ANNOUNCEMENT_TIMEZONE` in `.env` if the club ever moves. A date typed with no time lands at 9:00 AM. A bare time such as `19:30` means today, or tomorrow if that already passed.

The target channel is not configured in `.env`. It is set from **Set Announcement Channel** in the admin panel and remembered in the data file, so it can be changed at any time without touching the server.

The queue is stored in `data/announcements.json` (gitignored), relative to the folder the bots run from.

---

### 8. Universal Admin Control
**Command:** `!admin_setup`

Consolidates all bot admin panels into a single channel.

**Configuration:**
- Set `ADMIN_CHANNEL_ID` in `.env` to the ID of your secure admin channel.
- Run `!admin_setup` in that channel to generate all control panels.


## Installation & Setup

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
We provide interactive scripts that handle dependency installation, `.env` creation, and service setup. We also provide standalone scripts to run each bot individually for development or testing.

**Make scripts executable:**
```bash
chmod +x scripts/setup_main.sh scripts/setup_fork.sh scripts/run_*.py
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

## Configuration

### Environment Variables (`.env`)
The bot relies on a `.env` file for secrets and channel IDs.
*(See `.env.example` for the full template)*

```ini
# Tokens
# (Specific tokens for each bot are listed below)

# Channel IDs (Enable Developer Mode in Discord to copy IDs)
EVENT_CHANNEL_ID=123456789
WELCOME_CHANNEL_ID=123456789
GENERAL_CHANNEL_ID=123456789
INTRODUCTIONS_CHANNEL_ID=123456789
MAKER_GENERAL_CHANNEL_ID=123456789

# Role IDs
MEMBER_ROLE_ID=123456789
AUTO_JOIN_ROLE_ID=123456789

# Schedule Bot
SCHEDULE_BOT_TOKEN=your_token_here

# Filament Bot
FILAMENT_BOT_TOKEN=your_token_here
FILAMENT_DATA_PATH=./data
FILAMENT_PUBLIC_CHANNEL_ID=123456789
FILAMENT_ADMIN_CHANNEL_ID=987654321

# Announcement Bot
ANNOUNCEMENT_BOT_TOKEN=your_token_here
# The target channel is set from the admin panel, not here.
ANNOUNCEMENT_DATA_PATH=./data
# ANNOUNCEMENT_TIMEZONE=America/New_York  # optional, this is already the default

# Universal Admin
ADMIN_CHANNEL_ID=123456789 # Channel for !admin_setup command
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
STREAM_BOT_NICKNAME = "The G-Code Guardian"
SCHEDULE_BOT_NICKNAME = "The Timekeeper"
ANNOUNCEMENT_BOT_NICKNAME = "Megaphone Man"

# Welcome Messages
WELCOME_PUNS = [...] # Add your own puns here!
```

---

## Management & Updates

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
