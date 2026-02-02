# Discord Bots

This repository houses custom Discord bots for the **Engineering Leadership Council (ELC)**.

## Features

### 🤖 Welcome Bot
A friendly bot that welcomes new members with engineering-themed puns!
-   **Randomized Greetings**: "Ohm my god, a new member!", "Watt is up?", and more.
-   **Vibrant Embeds**: Messages appear in random, high-frequency colors.
-   **Helpful Links**: Directs new members to `#general`, `#introductions`, and the `#makerspace`.
-   **Smart Debounce**: Prevents duplicate welcome messages if Discord events fire multiple times.

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
    WELCOME_CHANNEL_ID=your_channel_id_here
    GENERAL_CHANNEL_ID=your_general_channel_id
    INTRODUCTIONS_CHANNEL_ID=your_intro_channel_id
    MAKER_GENERAL_CHANNEL_ID=your_maker_channel_id
    ```

## Usage

Run the bots with:
```bash
python main.py
```

## Troubleshooting

### "Member Joined" Event Not Firing?
Ensure **Server Members Intent** is enabled in the Discord Developer Portal:
1.  Go to your Application -> **Bot** tab.
2.  Scroll to **Privileged Gateway Intents**.
3.  Enable **SERVER MEMBERS INTENT**.
4.  Save Changes.
