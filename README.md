# Discord Bots

This repository houses custom Discord bots for the **Engineering Leadership Council (ELC)**.

## Features

*   **Jeff the Doorman (Welcome Bot)**:
    *   **Auto-Role**: Automatically assigns the "Member" role (configured in `.env`) to new users.
    *   **Targets specific welcome channels securely**.
    *   Greets new members with random Engineering Puns (Electrical/Mechanical).
    *   Displays a "Where to Start" guide linking to key channels.
    *   Uses vibrant, randomized embed colors.
    *   **Anti-Spam**: Prevents duplicate welcomes via a 10-second debounce.

*   **Sudo Master (Role Manager)**:
    *   **Self-Service Roles**: Interactive dropdown menu for Affiliate Clubs.
    *   **Admin Setup**: Deploy the menu to any channel using `!setup_clubs #channel`.
    *   **Reaction Roles**: Create custom role messages with `!setup_reaction #channel "Title" @Role1 @Role2`.
    *   **Toggle Logic**: Clicking a role adds it; clicking again removes it.

## Setup

### Prerequisites
-   Python 3.8 or higher
-   A Discord Bot Token (from the [Discord Developer Portal](https://discord.com/developers/applications))

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/Engineering-Leadership-Council/Discord-Bots.git
    cd Discord-Bots
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Create a `.env` file in the root directory:
    ```ini
    WELCOME_BOT_TOKEN=your_token_here
    ROLE_MANAGER_TOKEN=your_role_bot_token
    MEMBER_ROLE_ID=id_for_initial_member_role
    ROBOTICS_CLUB_ROLE_ID=id_for_robotics_role
    WELCOME_CHANNEL_ID=your_channel_id_here
    GENERAL_CHANNEL_ID=your_general_channel_id
    INTRODUCTIONS_CHANNEL_ID=your_intro_channel_id
    MAKER_GENERAL_CHANNEL_ID=your_maker_channel_id
    ```

## Usage

### 1. Run the Bots
**Production (Run All):**
```bash
python main.py
```

**Testing Only One Bot:**
```bash
# Sudo Master Only
python scripts/run_role_bot.py

# Jeff the Doorman Only
python scripts/run_welcome_bot.py
```

### 2. Setup Role Menu (Sudo Master)
To create the role signup menu:
1.  Go to your admin channel.
2.  Run the command: `!setup_clubs #target-channel`
3.  The bot will post the persistent menu in the target channel.

## Troubleshooting

### "Member Joined" Event Not Firing?
Ensure **Server Members Intent** is enabled in the Discord Developer Portal:
1.  Go to your Application -> **Bot** tab.
2.  Scroll to **Privileged Gateway Intents**.
3.  Enable **SERVER MEMBERS INTENT**.
4.  Save Changes.
