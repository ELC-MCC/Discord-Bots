import asyncio
import os
import sys
import discord
from dotenv import load_dotenv

# Add parent directory to sys.path to allow imports from bots folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.welcome_bot import WelcomeBot

# Load environment variables (from parent dir .env)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

async def run_welcome_bot():
    print("🤖 Starting Jeff the Doorman (Welcome Bot) ONLY...")
    
    # Setup Intents
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    # Jeff doesn't strictly need guilds intent to function for welcome, but it's good practice
    intents.guilds = True 

    # Get Token
    welcome_token = os.getenv('WELCOME_BOT_TOKEN')
    if not welcome_token:
        print("❌ Error: WELCOME_BOT_TOKEN not found in .env")
        return

    # Initialize Bot
    welcome_bot = WelcomeBot(intents=intents)

    # Start
    try:
        await welcome_bot.start(welcome_token.strip())
    except discord.LoginFailure:
        print("❌ Error: Invalid Token")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_welcome_bot())
    except KeyboardInterrupt:
        print("\n🛑 Stopping Jeff the Doorman...")
