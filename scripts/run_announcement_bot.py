import asyncio
import os
import sys
import discord
from dotenv import load_dotenv

# Add parent directory to sys.path to allow imports from bots folder
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from bots.announcement_bot import AnnouncementBot

dotenv_path = os.path.join(REPO_ROOT, '.env')
load_dotenv(dotenv_path)


async def run_announcement_bot():
    print("Starting Announcement Bot ONLY...")

    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True  # Needed for !admin_setup and !announce commands

    token = os.getenv('ANNOUNCEMENT_BOT_TOKEN')
    if not token:
        print("Error: ANNOUNCEMENT_BOT_TOKEN not found in {}".format(dotenv_path))
        return

    bot = AnnouncementBot(intents=intents)

    try:
        await bot.start(token.strip())
    except discord.LoginFailure:
        print("Error: Invalid token. Check your .env file.")
    except Exception as exc:
        print("Error: {}".format(exc))


if __name__ == "__main__":
    try:
        asyncio.run(run_announcement_bot())
    except KeyboardInterrupt:
        print("\nStopping Announcement Bot...")
