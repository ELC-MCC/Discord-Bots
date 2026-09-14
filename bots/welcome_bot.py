import discord
import time
import random
import os
import bot_config

# Discord channel IDs are snowflakes. .env.example ships these keys empty, and
# os.getenv only falls back to its default when a key is ABSENT, not when it is
# present and blank. int("") raises ValueError, which used to abort every welcome
# before the by-name channel search could run.
FALLBACK_CHANNEL_NAMES = ["new-people", "welcome", "general"]

# "Where to Start" links, in display order.
START_HERE_CHANNELS = [
    ("GENERAL_CHANNEL_ID", "General Chat"),
    ("INTRODUCTIONS_CHANNEL_ID", "Introductions"),
    ("MAKER_GENERAL_CHANNEL_ID", "Maker General"),
]

# Both on_member_join and on_member_update can fire for one person.
DEBOUNCE_SECONDS = 10
MAX_TRACKED_MEMBERS = 200


def env_channel_id(name):
    """Read a channel ID from the environment, tolerating blank or malformed values."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"WelcomeBot: {name} is not a numeric channel ID ({raw!r}); ignoring it.")
        return None


class WelcomeBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_welcome_time = {}  # member ID -> time of last successful welcome

    def already_welcomed(self, member_id):
        last = self.last_welcome_time.get(member_id)
        return last is not None and (time.time() - last) < DEBOUNCE_SECONDS

    def remember_welcome(self, member_id):
        self.last_welcome_time[member_id] = time.time()
        # Keep the ledger bounded instead of growing for the life of the process.
        if len(self.last_welcome_time) > MAX_TRACKED_MEMBERS:
            overflow = len(self.last_welcome_time) - MAX_TRACKED_MEMBERS
            oldest = sorted(self.last_welcome_time.items(), key=lambda kv: kv[1])[:overflow]
            for old_id, _ in oldest:
                self.last_welcome_time.pop(old_id, None)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        # Set nickname in all servers
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.WELCOME_BOT_NICKNAME)
                print(f"Changed nickname to '{bot_config.WELCOME_BOT_NICKNAME}' in {guild.name}")
            except discord.Forbidden:
                print(f"Missing permissions to change nickname in {guild.name}")
            except Exception as e:
                print(f"Failed to change nickname in {guild.name}: {e}")

    async def on_member_join(self, member):
        """
        Event triggered when a new member joins the server.
        Sends a welcome message to a specific channel.
        """
        print(f"DEBUG: WelcomeBot.on_member_join triggered for {member.name} (ID: {member.id})")
        print(f"DEBUG: Member Pending Status: {member.pending}")

        # If pending verification (Onboarding), wait.
        if member.pending:
            print(f"WelcomeBot: {member.name} is pending verification. Waiting...")
            return

        print(f"WelcomeBot: {member.name} is NOT pending. Sending welcome...")
        await self.send_welcome(member)

    async def on_member_update(self, before, after):
        """Handle member update events, specifically regarding verification."""
        # Log state changes for debugging
        if before.pending != after.pending:
            print(f"DEBUG: WelcomeBot.on_member_update: {after.name} Pending changed: {before.pending} -> {after.pending}")

        # Check if member completed verification (pending: True -> False)
        if before.pending and not after.pending:
            print(f"WelcomeBot: {after.name} completed verification.")
            await self.send_welcome(after)

    async def send_welcome(self, member):
        # Debounce: on_member_join and on_member_update can both fire for one person.
        if self.already_welcomed(member.id):
            print(f"Ignored duplicate welcome event for {member.name} (ID: {member.id})")
            return

        print(f"Welcoming member: {member.name} (ID: {member.id})")

        guild = member.guild

        # Prefer the configured channel, otherwise look one up by name.
        target_channel_id = env_channel_id('WELCOME_CHANNEL_ID')
        channel = guild.get_channel(target_channel_id) if target_channel_id else None

        if not channel:
            if target_channel_id:
                print(f"Channel ID {target_channel_id} not found. Searching by name...")
            else:
                print("No usable WELCOME_CHANNEL_ID. Searching by name...")
            for name in FALLBACK_CHANNEL_NAMES:
                found = discord.utils.get(guild.text_channels, name=name)
                if found:
                    channel = found
                    break

        if not channel:
            print(f"Could not find any of the following channels: "
                  f"{', '.join(FALLBACK_CHANNEL_NAMES)} to greet {member.name}")
            return

        # Puns from config
        puns = bot_config.WELCOME_PUNS
        title = random.choice(puns) if puns else "Welcome to the ELC!"

        # Random vibrant color
        colors = [0x00FFFF, 0xFF00FF, 0x00FF00, 0xFFA500, 0xFFFF00, 0x0000FF]
        color = random.choice(colors)

        embed = discord.Embed(
            title=title,
            description=f"Welcome to the ELC, **{member.display_name}**! We are excited to have you here. Please check out the rules and introduce yourself!",
            color=color
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

        # Only list channels that are actually configured. A row of broken <#None>
        # mentions looks worse than no field at all.
        links = []
        for env_key, label in START_HERE_CHANNELS:
            channel_id = env_channel_id(env_key)
            if channel_id:
                links.append(f"• <#{channel_id}> - {label}")
        if links:
            embed.add_field(name="Where to Start", value="\n".join(links), inline=False)

        # No footer as requested

        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Error: Missing permissions to send messages in #{channel.name}")
        except Exception as e:
            print(f"Error sending welcome message: {e}")
        else:
            # Record only after a real send, so a failure can still be retried.
            self.remember_welcome(member.id)
            print(f"Sent welcome message for {member.name} in #{channel.name}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Universal Admin Setup
        if message.content.startswith('!admin_setup'):
             if not message.author.guild_permissions.administrator:
                 return
            
             # Check configured admin channel
             admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
             if admin_channel_id and str(message.channel.id) != str(admin_channel_id):
                return

             # Wait for purge
             import asyncio
             await asyncio.sleep(2)

             # Get current config status
             welcome_chan = os.getenv('WELCOME_CHANNEL_ID', 'Not Set')
             
             # Check Auto-Role Status
             member_role_id = os.getenv('MEMBER_ROLE_ID')
             role_status = "❌ Not Configured (Set `MEMBER_ROLE_ID` in .env)"
             
             if member_role_id:
                 try:
                     role = message.guild.get_role(int(member_role_id))
                     if role:
                         role_status = f"✅ Active: {role.mention}"
                     else:
                         role_status = f"⚠️ Error: Role ID `{member_role_id}` not found in this server."
                 except ValueError:
                     role_status = f"⚠️ Error: Invalid Role ID format in .env"

             embed = discord.Embed(
                 title="Jeff the Doorman (Welcome Bot)",
                 description=f"Welcomes new members with puns.\n\n**Status:**\n• **Welcome Channel ID:** `{welcome_chan}`\n• **Auto-Role:** {role_status}",
                 color=0xE91E63
             )
             await message.channel.send(embed=embed)
             return
