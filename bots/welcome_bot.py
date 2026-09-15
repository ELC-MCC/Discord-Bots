import discord
import asyncio
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

    def resolve_welcome_channel(self, guild):
        """The channel a welcome would actually be posted to, or None."""
        configured = env_channel_id('WELCOME_CHANNEL_ID')
        channel = guild.get_channel(configured) if configured else None
        if channel:
            return channel
        for name in FALLBACK_CHANNEL_NAMES:
            found = discord.utils.get(guild.text_channels, name=name)
            if found:
                return found
        return None

    def diagnose(self, guild):
        """Reasons welcomes would silently not arrive. Empty list means healthy.

        Everything the bot needs in order to greet someone is checkable up front,
        so this exists to turn "it does not work" into a specific sentence.
        """
        problems = []
        configured = env_channel_id('WELCOME_CHANNEL_ID')

        if not configured:
            problems.append(
                "`WELCOME_CHANNEL_ID` is empty or missing in .env, so a channel named "
                + ", ".join(FALLBACK_CHANNEL_NAMES) + " is used instead."
            )

        channel = self.resolve_welcome_channel(guild)
        if channel is None:
            problems.append(
                "No welcome channel found, so every welcome is skipped. Set "
                "`WELCOME_CHANNEL_ID` to the numeric channel ID (Developer Mode on, then "
                "right click the channel, Copy Channel ID)."
            )
            self._append_intent_problem(problems)
            return problems

        if configured and guild.get_channel(configured) is None:
            problems.append(
                f"`WELCOME_CHANNEL_ID` ({configured}) does not exist in this server, "
                f"so #{channel.name} was used instead."
            )

        try:
            perms = channel.permissions_for(guild.me)
            for label, allowed in (
                ("View Channel", perms.view_channel),
                ("Send Messages", perms.send_messages),
                ("Embed Links", perms.embed_links),
            ):
                if not allowed:
                    problems.append(f"Missing the {label} permission in #{channel.name}")
        except Exception as exc:
            problems.append(f"Could not read permissions for #{channel.name}: {exc}")

        self._append_intent_problem(problems)
        return problems

    def _append_intent_problem(self, problems):
        if not getattr(self.intents, "members", False):
            problems.append(
                "The Server Members intent is off, so on_member_join never fires at all."
            )

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

            # Say up front whether welcomes can actually go out.
            problems = self.diagnose(guild)
            if problems:
                print(f"WelcomeBot: {len(problems)} problem(s) found in {guild.name}:")
                for problem in problems:
                    print("  - " + problem.replace("`", ""))
            else:
                channel = self.resolve_welcome_channel(guild)
                print(f"WelcomeBot: ready in {guild.name}, welcomes will post to #{channel.name}")

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
        if message.author == self.user or not message.content:
            return

        # On-demand health check, so you do not have to read the process logs.
        if message.content.startswith('!welcome_check'):
            if not message.author.guild_permissions.administrator:
                return
            await message.channel.send(embed=self.check_embed(message.guild))
            return

        # Universal Admin Setup
        if message.content.startswith('!admin_setup'):
            if not message.author.guild_permissions.administrator:
                return

            # Check configured admin channel
            admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
            if admin_channel_id and str(message.channel.id) != str(admin_channel_id):
                return

            # Wait for the other bots to finish their purge of this channel.
            await asyncio.sleep(2)
            await message.channel.send(embed=self.panel_embed(message.guild))
            return

    def check_embed(self, guild):
        """Report whether a welcome could actually be delivered right now."""
        channel = self.resolve_welcome_channel(guild)
        problems = self.diagnose(guild)

        embed = discord.Embed(
            title="Welcome Bot Check",
            color=0xE74C3C if problems else 0x2ECC71,
        )
        embed.add_field(
            name="Welcome channel",
            value=channel.mention if channel else "*none found*",
            inline=False,
        )
        body = (
            "\n".join("- " + problem for problem in problems)
            if problems
            else "No problems found. Welcomes should post normally."
        )
        embed.add_field(name="Result", value=body[:1020], inline=False)
        embed.set_footer(text="Run this again after any .env or permission change.")
        return embed

    def panel_embed(self, guild):
        channel = self.resolve_welcome_channel(guild)
        problems = self.diagnose(guild)

        embed = discord.Embed(
            title=f"{bot_config.WELCOME_BOT_NICKNAME} (Welcome Bot)",
            description=(
                "Welcomes new members with puns.\n\n"
                "**Commands:**\n"
                "`!welcome_check` - report whether welcomes can actually be delivered."
            ),
            color=0xE91E63,
        )
        embed.add_field(
            name="Welcome channel",
            value=channel.mention if channel else "*none found*",
            inline=True,
        )
        embed.add_field(
            name="Health",
            value="OK" if not problems else f"{len(problems)} problem(s)",
            inline=True,
        )
        if problems:
            embed.add_field(
                name="Problems",
                value="\n".join("- " + problem for problem in problems)[:1020],
                inline=False,
            )
        embed.add_field(
            name="Role handling",
            value="Auto-role on join is handled by Sudo Master (Role Bot), not by this bot.",
            inline=False,
        )
        return embed
