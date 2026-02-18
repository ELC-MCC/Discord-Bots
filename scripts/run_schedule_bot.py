import asyncio
import os
import sys
import discord
from dotenv import load_dotenv

# Add parent directory to sys.path to allow imports from bots and root folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.schedule_bot import ScheduleBot

# Load environment variables (from parent dir .env)
# Construct the path manually to ensure it loads the correct .env
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, '.env'))

async def run_schedule_bot():
    print("🤖 Starting Schedule Bot ONLY...")

    # Setup Intents (Matches main.py and schedule_bot.py needs)
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.members = True 

    # Get Token
    schedule_token = os.getenv('SCHEDULE_BOT_TOKEN')
    
    if not schedule_token:
        print("❌ Error: SCHEDULE_BOT_TOKEN not found in .env")
        print("Please add 'SCHEDULE_BOT_TOKEN=your_token' to your .env file.")
        return

    # Initialize Bot
    # Note: ScheduleBot relies on bot_config (imported inside schedule_bot.py),
    # which is available because we added root_dir to sys.path.
    bot = ScheduleBot(intents=intents)

    # Start
    try:
        await bot.start(schedule_token.strip())
    except discord.LoginFailure:
        print("❌ Error: Invalid Token. Please checking your .env file.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_schedule_bot())
    except KeyboardInterrupt:
        print("\n🛑 Stopping Schedule Bot...")
