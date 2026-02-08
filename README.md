# Discord Bots

This repository contains the custom Discord bots developed for the **Engineering Leadership Council (ELC)**. These services are designed to automate server management, onboard new members, and schedule organization events.

## Features

### 1. Jeff the Doorman (Welcome Bot)
*   **Smart Greetings**: Welcomes new members with randomized engineering-themed messages (covering Electrical, Mechanical, Civil, and other disciplines).
*   **Auto-Role**: Automatically assigns the "Member" role to new users upon joining, configurable via environment variables.
*   **Orientation**: Provides a "Where to Start" section with links to key channels (e.g., General, Introductions).
*   **Visual Integration**: Generates embedded messages with randomized colors for visual variety.
*   **Anti-Spam**: Includes a debounce mechanism to prevent duplicate welcome messages.

### 2. Sudo Master (Role Manager)
*   **Reaction Roles**: Facilitates ad-hoc role assignment via reaction monitoring.
    *   *Usage*: `!setup_reaction #channel "Title" @Role1 @Role2 ...`
    *   *Architecture*: Stateless design; the bot reads its own messages to map reactions to roles, requiring no database.
*   **Access Control**: Critical commands are restricted to users with Administrator permissions.

### 3. Event Messenger Bot
*   **Event Scheduling**: Allows administrators to schedule upcoming events via commands.
    *   *Usage*: `!add_event "Name" "YYYY-MM-DD HH:MM" "Description"`
    *   *Example*: `!add_event "General Meeting" "2024-10-15 18:00" "Byrne Hall"`
*   **Automated Notifications**: Automatically posts an announcement to a designated channel when the scheduled event time arrives.
*   **Persistence**: Stores event data locally in `events.json` to ensure data integrity across reliable restarts.
*   **Management**:
    *   `!list_events`: Displays a list of all upcoming scheduled events.
    *   `!delete_event <ID>`: Removes an event from the schedule.

---

## Setup and Installation

### Prerequisites
*   Python 3.8 or higher
*   Discord Bot Token(s) obtained from the Discord Developer Portal.
*   **Intents**: The `Presence`, `Server Members`, and `Message Content` intents must be enabled in the Discord Developer Portal.

### 1. Installation
Clone the repository and install the required dependencies:
```bash
git clone https://github.com/Engineering-Leadership-Council/Discord-Bots.git
cd Discord-Bots
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file in the root directory. You may use separate tokens for each bot or a single token if running as a combined application.

```ini
# --- Welcome Bot ---
WELCOME_BOT_TOKEN=your_token_here
WELCOME_CHANNEL_ID=123456789
GENERAL_CHANNEL_ID=123456789
INTRODUCTIONS_CHANNEL_ID=123456789
MAKER_GENERAL_CHANNEL_ID=123456789

# --- Role Manager ---
ROLE_MANAGER_TOKEN=your_token_here
MEMBER_ROLE_ID=id_to_give_new_users

# --- Event Bot ---
EVENT_BOT_TOKEN=your_token_here
EVENT_CHANNEL_ID=channel_to_post_announcements
```

---

## Usage

### Production (Run All Bots)
To execute all bots simultaneously (e.g., for deployment):
```bash
python main.py
```

### Development (Run Individually)
To test specific components in isolation:
```bash
# Run Sudo Master (Role Bot)
python scripts/run_role_bot.py

# Run Jeff the Doorman (Welcome Bot)
python scripts/run_welcome_bot.py

# Run Event Messenger
python scripts/run_event_bot.py
```

---

## Deployment Information

The application is designed to run as a system service.

### Service Management
If running on a Linux-based system (e.g., Raspberry Pi) via systemd:

1.  **Update**: Pull the latest changes from the repository.
2.  **Restart**: Restart the service to apply changes.

```bash
cd ~/Discord-Bots
git pull
sudo systemctl restart discord-bots
```

### Logging
Monitor the service logs using the journalctl command:
```bash
journalctl -u discord-bots -f
```

### Troubleshooting
*   **Service Failures**: Check system logs for stack traces or error messages.
*   **Permission Errors**: Ensure the Bot role has the "Manage Roles" and "Send Messages" permissions within the Discord server.
*   **Notification Issues**: Verify that `EVENT_CHANNEL_ID` is correct and that the bot has permission to view and post in the target channel.
