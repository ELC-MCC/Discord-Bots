import asyncio
import os
import discord
from dotenv import load_dotenv
from bots.welcome_bot import WelcomeBot
from bots.role_bot import RoleBot

# Load environment variables
load_dotenv()

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

    bots = []

    # Add Welcome Bot
    if welcome_token:
        # Note: 'intents' is shared, but that's fine as long as it has what both need
        welcome_bot = WelcomeBot(intents=intents)
        bots.append(welcome_bot.start(welcome_token.strip()))
    else:
        print("Warning: WELCOME_BOT_TOKEN not found in .env")

    # Add Role Manager
    if role_token:
        # RoleBot needs member access too, effectively enabled by default intents + members=True above
        role_bot = RoleBot(intents=intents)
        bots.append(role_bot.start(role_token.strip()))
    else:
        print("Warning: ROLE_MANAGER_TOKEN not found in .env")



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
