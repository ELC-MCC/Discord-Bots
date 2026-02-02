import asyncio
import os
import sys
import discord
from dotenv import load_dotenv

# Add parent directory to sys.path to allow imports from bots folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bots.role_bot import RoleBot

# Load environment variables (from parent dir .env)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

async def run_role_bot():
    print("🤖 Starting Sudo Master (Role Bot) ONLY...")
    
    # Setup Intents
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    intents.guilds = True

    # Get Token
    role_token = os.getenv('ROLE_MANAGER_TOKEN')
    if not role_token:
        print("❌ Error: ROLE_MANAGER_TOKEN not found in .env")
        return

    # Initialize Bot
    role_bot = RoleBot(intents=intents)

    # Start
    try:
        await role_bot.start(role_token.strip())
    except discord.LoginFailure:
        print("❌ Error: Invalid Token")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_role_bot())
    except KeyboardInterrupt:
        print("\n🛑 Stopping Sudo Master...")
