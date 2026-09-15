import asyncio
import os
import discord
from dotenv import load_dotenv
from bots.welcome_bot import WelcomeBot
from bots.role_bot import RoleBot
from bots.event_bot import EventBot
from bots.stream_bot import StreamBot
from bots.schedule_bot import ScheduleBot
from bots.filament_bot import FilamentBot
from bots.announcement_bot import AnnouncementBot
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


async def supervise_bot(label, token, build):
    """Start a single bot, and contain its failure so it cannot take the rest down.

    These used to be started directly inside asyncio.gather, so one invalid token
    or one application missing a privileged intent raised out of run_bots, the
    event loop closed, and every bot died with it. That made one broken bot look
    like all of them being broken, with no line saying which one caused it.
    """
    try:
        client = build()
    except Exception as exc:
        print(f"[{label}] could not be created: {type(exc).__name__}: {exc}")
        return

    try:
        await client.start(token)
    except discord.LoginFailure:
        print(f"[{label}] LOGIN FAILED: the token in .env is not valid. Check for a typo, "
              f"a leftover quote, or a token that was reset in the Developer Portal.")
    except discord.PrivilegedIntentsRequired as exc:
        print(f"[{label}] PRIVILEGED INTENTS MISSING: Developer Portal > this application > "
              f"Bot > Privileged Gateway Intents, then enable Server Members and "
              f"Message Content. ({exc})")
    except Exception as exc:
        print(f"[{label}] stopped after an error: {type(exc).__name__}: {exc}")
    else:
        print(f"[{label}] stopped.")


def plan_bots(intents):
    """Work out which bots can actually start.

    Returns a list of (label, token, build) for every bot that is both enabled and
    has a non-empty token. Everything else is reported loudly, because a blank
    token used to produce only a soft warning that was easy to miss while every
    other bot kept working normally.
    """
    # label, env var that holds the token, enabled flag, how to build the client
    plan = [
        ("Welcome Bot", "WELCOME_BOT_TOKEN", bot_config.ENABLE_WELCOME_BOT,
         lambda: WelcomeBot(intents=intents)),
        ("Role Bot", "ROLE_MANAGER_TOKEN", bot_config.ENABLE_ROLE_BOT,
         lambda: RoleBot(intents=intents)),
        ("Event Bot", "EVENT_BOT_TOKEN", bot_config.ENABLE_EVENT_BOT,
         lambda: EventBot(intents=intents)),
        ("Stream Bot", "STREAM_BOT_TOKEN", bot_config.ENABLE_STREAM_BOT,
         lambda: StreamBot(intents=intents)),
        ("Schedule Bot", "SCHEDULE_BOT_TOKEN", bot_config.ENABLE_SCHEDULE_BOT,
         lambda: ScheduleBot(intents=intents)),
        ("Filament Bot", "FILAMENT_BOT_TOKEN", bot_config.ENABLE_FILAMENT_BOT,
         lambda: FilamentBot(intents=intents)),
        ("Announcement Bot", "ANNOUNCEMENT_BOT_TOKEN", bot_config.ENABLE_ANNOUNCEMENT_BOT,
         lambda: AnnouncementBot(intents=intents)),
    ]

    specs = []
    for label, env_var, enabled, build in plan:
        if not enabled:
            print(f"[startup] {label}: disabled in bot_config.py")
            continue
        # Blank counts as missing: a bare "TOKEN=" line is falsy, and this bot
        # would otherwise vanish from the running set with no explanation.
        token = (os.getenv(env_var) or "").strip()
        if not token:
            print(f"[startup] {label}: SKIPPED. {env_var} is empty or missing in .env, "
                  f"so this bot will not run at all")
            continue
        specs.append((label, token, build))
    return specs


async def run_bots():
    # Setup Intents
    intents = discord.Intents.default()
    intents.members = True  # Required for on_member_join and on_member_update
    intents.message_content = True
    intents.guilds = True

    specs = plan_bots(intents)

    if not specs:
        print("[startup] No usable bot tokens found. Exiting so the process manager can retry.")
        return

    print(f"[startup] Starting {len(specs)} bot(s): {', '.join(label for label, _, _ in specs)}")
    await asyncio.gather(*(supervise_bot(*spec) for spec in specs))
    print("[startup] Every bot has stopped.")


def main():
    try:
        asyncio.run(run_bots())
    except KeyboardInterrupt:
        # Handle manual stop (Ctrl+C) gracefully
        print("Stopping bots...")


if __name__ == "__main__":
    main()
