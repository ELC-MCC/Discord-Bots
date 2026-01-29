import asyncio
import os
import discord
from dotenv import load_dotenv
from bots.welcome_bot import WelcomeBot

# Load environment variables
load_dotenv()

async def run_bots():
    # Setup Intents
    intents = discord.Intents.default()
    intents.members = True  # Required for on_member_join
    intents.message_content = True

    # 1. Welcome Bot
    welcome_token = os.getenv('WELCOME_BOT_TOKEN')
    if not welcome_token:
        print("Error: WELCOME_BOT_TOKEN not found in .env")
        return
    welcome_token = welcome_token.strip()

    welcome_bot = WelcomeBot(intents=intents)

    # List of bot run tasks
    bots = []
    
    # Add Welcome Bot to tasks
    # client.start() is the coroutine to start the connection
    bots.append(welcome_bot.start(welcome_token))

    # Add other bots here in the future
    # other_bot = OtherBot(...)
    # bots.append(other_bot.start(other_token))

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
