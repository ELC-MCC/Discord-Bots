import asyncio
import os
import discord
from dotenv import load_dotenv
from bots.welcome_bot import WelcomeBot
from bots.role_bot import RoleBot
from bots.event_bot import EventBot
from bots.stream_bot import StreamBot
import bot_config

import logging

# Load environment variables
load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Set specific components to DEBUG to help with printer issues
logging.getLogger("StreamBot").setLevel(logging.DEBUG)
logging.getLogger("SDCPClient").setLevel(logging.DEBUG)

async def run_bots():
    # Setup Intents
    intents = discord.Intents.default()
    intents.members = True  # Required for on_member_join
    intents.message_content = True
    intents.guilds = True

    # 1. Welcome Bot
    welcome_token = os.getenv('WELCOME_BOT_TOKEN')
    
    # 2. Role Manager (Sudo Master)
    role_token = os.getenv('ROLE_MANAGER_TOKEN')
    
    # 3. Event Bot
    event_token = os.getenv('EVENT_BOT_TOKEN')

    bots = []

    # Add Welcome Bot
    if bot_config.ENABLE_WELCOME_BOT:
        if welcome_token:
            # Note: 'intents' is shared, but that's fine as long as it has what both need
            welcome_bot = WelcomeBot(intents=intents)
            bots.append(welcome_bot.start(welcome_token.strip()))
        else:
            print("Warning: WELCOME_BOT_TOKEN not found in .env (but bot is ENABLED)")
    else:
        print("Welcome Bot is DISABLED in bot_config.py")

    # Add Role Manager
    if bot_config.ENABLE_ROLE_BOT:
        if role_token:
            # RoleBot needs member access too, effectively enabled by default intents + members=True above
            role_bot = RoleBot(intents=intents)
            bots.append(role_bot.start(role_token.strip()))
        else:
            print("Warning: ROLE_MANAGER_TOKEN not found in .env (but bot is ENABLED)")
    else:
        print("Role Bot is DISABLED in bot_config.py")

    # Add Event Bot
    if bot_config.ENABLE_EVENT_BOT:
        if event_token:
            event_bot = EventBot(intents=intents)
            bots.append(event_bot.start(event_token.strip()))
        else:
            print("Warning: EVENT_BOT_TOKEN not found in .env (but bot is ENABLED)")
    else:
        print("Event Bot is DISABLED in bot_config.py")

    # Add Stream Bot
    stream_token = os.getenv('STREAM_BOT_TOKEN')
    if bot_config.ENABLE_STREAM_BOT:
        if stream_token:
            # StreamBot needs message content to read !start_stream commands if we had them, 
            # but mainly just needs to send messages.
            stream_bot = StreamBot(intents=intents)
            bots.append(stream_bot.start(stream_token.strip()))
        else:
            print("Warning: STREAM_BOT_TOKEN not found in .env (but bot is ENABLED)")
    else:
        print("Stream Bot is DISABLED in bot_config.py")



    if not bots:
        print("Error: No bot tokens found. Exiting.")
        return

    print("Starting bots...")
    await asyncio.gather(*bots)

def main():
    try:
        asyncio.run(run_bots())
    except KeyboardInterrupt:
        # Handle manual stop (Ctrl+C) gracefully
        print("Stopping bots...")

if __name__ == "__main__":
    main()
