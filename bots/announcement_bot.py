import discord
from discord import ui
from discord.ext import tasks
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import bot_config
from utils import announcement_scheduler as sched


DATA_FILENAME = "announcements.json"

PANEL_COLOR = 0x3498DB
EMBED_COLOR = 0x3498DB
WARN_COLOR = 0xE67E22
ERROR_COLOR = 0xE74C3C


def _blank_data() -> Dict:
    return {
        "channel_id": None,
        "channel_name": None,
        "admin_channel_id": None,
        "admin_message_id": None,
        "announcements": [],
    }


def _channel_mention(channel_id) -> str:
    return "<#{}>".format(channel_id) if channel_id else "*not set*"


# --- Modals ------------------------------------------------------------------


class AnnouncementModal(ui.Modal, title="New Announcement"):
    """The three prompts: title, when to send, and the announcement itself."""

    title_input = ui.TextInput(
        label="Title",
        placeholder="Makerspace closed for winter break",
        max_length=200,
    )
    when_input = ui.TextInput(
        label="When to send",
        placeholder="30m  |  2h  |  tomorrow 8:00  |  2026-09-14 19:30  |  now",
        max_length=60,
    )
    body_input = ui.TextInput(
        label="Announcement",
        style=discord.TextStyle.paragraph,
        placeholder="The full announcement text. Markdown works, links work.",
        max_length=4000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        bot: "AnnouncementBot" = interaction.client

        try:
            send_at = sched.parse_when(self.when_input.value)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        except Exception as exc:  # pragma: no cover - defensive
            await interaction.response.send_message("Could not read that time: {}".format(exc), ephemeral=True)
            return

        payload = {
            "title": self.title_input.value.strip(),
            "body": self.body_input.value,
            "raw_when": self.when_input.value.strip(),
            "send_at": sched.to_iso(send_at),
        }

        embed = bot.preview_embed(payload, send_at)
        await interaction.response.send_message(
            embed=embed,
            view=ConfirmAnnouncementView(bot, payload),
            ephemeral=True,
        )


# --- Confirmation ------------------------------------------------------------


class ConfirmAnnouncementView(ui.View):
    def __init__(self, bot: "AnnouncementBot", payload: Dict):
        super().__init__(timeout=300)
        self.bot = bot
        self.payload = payload

    def _target(self) -> Optional[int]:
        return self.bot.data.get("channel_id")

    async def _finish(self, interaction: discord.Interaction, entry: Optional[Dict], note: str):
        for item in self.children:
            item.disabled = True
        if entry is not None:
            embed = self.bot.status_embed(entry)
        else:
            embed = self.bot.preview_embed(self.payload, sched.from_iso(self.payload["send_at"]))
        await interaction.response.edit_message(content=note, embed=embed, view=self)

    @ui.button(label="Schedule", style=discord.ButtonStyle.success)
    async def schedule(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can schedule announcements.", ephemeral=True)
            return

        channel_id = self._target()
        if not channel_id:
            await interaction.response.send_message(
                "No announcement channel set yet. Use **Set Announcement Channel** in the admin panel first.",
                ephemeral=True,
            )
            return

        entry = self.bot.add_announcement(
            title=self.payload["title"],
            body=self.payload["body"],
            send_at=self.payload["send_at"],
            author=interaction.user,
            channel_id=channel_id,
            ping=False,
        )
        send_at = sched.from_iso(entry["send_at"])
        await self._finish(
            interaction,
            entry,
            "Scheduled. Fires {} ({}).".format(sched.format_with_zone(send_at), sched.humanize(send_at)),
        )
        await self.bot.update_panel()

    @ui.button(label="Schedule + @everyone", style=discord.ButtonStyle.primary)
    async def schedule_ping(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can schedule announcements.", ephemeral=True)
            return

        channel_id = self._target()
        if not channel_id:
            await interaction.response.send_message(
                "No announcement channel set yet. Use **Set Announcement Channel** in the admin panel first.",
                ephemeral=True,
            )
            return

        entry = self.bot.add_announcement(
            title=self.payload["title"],
            body=self.payload["body"],
            send_at=self.payload["send_at"],
            author=interaction.user,
            channel_id=channel_id,
            ping=True,
        )
        send_at = sched.from_iso(entry["send_at"])
        await self._finish(
            interaction,
            entry,
            "Scheduled with @everyone. Fires {} ({}).".format(
                sched.format_with_zone(send_at), sched.humanize(send_at)
            ),
        )
        await self.bot.update_panel()

    @ui.button(label="Send Now", style=discord.ButtonStyle.secondary)
    async def send_now(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can send announcements.", ephemeral=True)
            return

        channel_id = self._target()
        if not channel_id:
            await interaction.response.send_message(
                "No announcement channel set yet. Use **Set Announcement Channel** in the admin panel first.",
                ephemeral=True,
            )
            return

        entry = self.bot.add_announcement(
            title=self.payload["title"],
            body=self.payload["body"],
            send_at=self.payload["send_at"],
            author=interaction.user,
            channel_id=channel_id,
            ping=False,
        )
        await interaction.response.defer(ephemeral=True)
        ok = await self.bot.deliver(entry)
        await interaction.followup.send(
            "Sent to {}.".format(_channel_mention(channel_id)) if ok else "Could not send: {}".format(entry.get("error")),
            ephemeral=True,
        )
        await self.bot.update_panel()

    @ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Cancelled. Nothing was scheduled.", embed=None, view=self)


# --- Channel selection -------------------------------------------------------


class AnnouncementChannelSelect(ui.View):
    def __init__(self, bot: "AnnouncementBot"):
        super().__init__(timeout=120)
        self.bot = bot

    @ui.select(
        cls=ui.ChannelSelect,
        channel_types=[discord.ChannelType.text, discord.ChannelType.news],
        placeholder="Select the channel announcements should go to...",
    )
    async def select_channel(self, interaction: discord.Interaction, select: ui.ChannelSelect):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can set the announcement channel.", ephemeral=True)
            return

        picked = select.values[0]
        channel = await self.bot.resolve_channel(picked.id)
        if channel is None:
            await interaction.response.send_message("Could not resolve that channel, try again.", ephemeral=True)
            return

        self.bot.data["channel_id"] = channel.id
        self.bot.data["channel_name"] = getattr(channel, "name", str(channel.id))
        self.bot.save()

        # Prove the target actually works before calling it configured.
        warning = ""
        try:
            perms = channel.permissions_for(interaction.guild.me)
            missing = [
                name
                for name, ok in (
                    ("View Channel", perms.view_channel),
                    ("Send Messages", perms.send_messages),
                    ("Embed Links", perms.embed_links),
                )
                if not ok
            ]
            if missing:
                warning = "\nWarning: I am missing {} there.".format(", ".join(missing))
        except Exception:
            pass

        await interaction.response.send_message(
            "Announcement channel set to {}.{}".format(channel.mention, warning), ephemeral=True
        )
        await self.bot.update_panel()
        self.stop()


# --- Managing the queue ------------------------------------------------------


class SingleAnnouncementView(ui.View):
    def __init__(self, bot: "AnnouncementBot", entry: Dict):
        super().__init__(timeout=180)
        self.bot = bot
        self.entry = entry

    @ui.button(label="Send Now", style=discord.ButtonStyle.primary)
    async def send_now(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can send announcements.", ephemeral=True)
            return
        if self.entry.get("status") != "pending":
            await interaction.response.send_message("That announcement is no longer pending.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ok = await self.bot.deliver(self.entry)
        await interaction.followup.send(
            "Sent." if ok else "Failed: {}".format(self.entry.get("error")), ephemeral=True
        )
        await self.bot.update_panel()

    @ui.button(label="Cancel Announcement", style=discord.ButtonStyle.danger)
    async def cancel_it(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can cancel announcements.", ephemeral=True)
            return

        ok = self.bot.cancel_announcement(self.entry["id"], interaction.user)
        for item in self.children:
            item.disabled = True
        if ok:
            await interaction.response.edit_message(
                content="Cancelled: {}".format(self.entry["title"]), embed=None, view=self
            )
            await self.bot.update_panel()
        else:
            await interaction.response.edit_message(
                content="Could not cancel (already sent or gone).", embed=None, view=self
            )


class ManageAnnouncementSelect(ui.Select):
    def __init__(self, bot: "AnnouncementBot", entries: List[Dict]):
        self.bot = bot
        self.entries = {e["id"]: e for e in entries}
        options = []
        for entry in entries[:25]:
            when = sched.from_iso(entry["send_at"])
            label = "{} - {}".format(entry["title"], sched.humanize(when))
            options.append(
                discord.SelectOption(
                    label=label[:100],
                    description="{} | {}".format(sched.format_local(when), entry.get("channel_name") or "channel")[:100],
                    value=entry["id"],
                )
            )
        super().__init__(placeholder="Select a scheduled announcement...", options=options)

    async def callback(self, interaction: discord.Interaction):
        entry = self.entries.get(self.values[0])
        if not entry:
            await interaction.response.send_message("That announcement is gone.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=self.bot.status_embed(entry),
            view=SingleAnnouncementView(self.bot, entry),
            ephemeral=True,
        )


class ManageAnnouncementsView(ui.View):
    def __init__(self, bot: "AnnouncementBot", entries: List[Dict]):
        super().__init__(timeout=180)
        self.add_item(ManageAnnouncementSelect(bot, entries))


# --- Admin panel -------------------------------------------------------------


class AnnouncementAdminView(ui.View):
    def __init__(self, bot: "AnnouncementBot"):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="New Announcement", style=discord.ButtonStyle.success, custom_id="announce_admin_new")
    async def new_announcement(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can write announcements.", ephemeral=True)
            return
        await interaction.response.send_modal(AnnouncementModal())

    @ui.button(label="Set Announcement Channel", style=discord.ButtonStyle.primary, custom_id="announce_admin_channel")
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can set the announcement channel.", ephemeral=True)
            return
        await interaction.response.send_message(
            "Where should announcements be posted?",
            view=AnnouncementChannelSelect(self.bot),
            ephemeral=True,
        )

    @ui.button(label="Scheduled", style=discord.ButtonStyle.secondary, custom_id="announce_admin_list")
    async def list_pending(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can view the queue.", ephemeral=True)
            return

        entries = sched.pending_announcements(self.bot.data["announcements"])
        if not entries:
            await interaction.response.send_message("Nothing scheduled.", ephemeral=True)
            return
        await interaction.response.send_message(
            "{} scheduled. Pick one to send early or cancel it:".format(len(entries)),
            view=ManageAnnouncementsView(self.bot, entries),
            ephemeral=True,
        )

    @ui.button(label="History", style=discord.ButtonStyle.secondary, custom_id="announce_admin_history", row=1)
    async def history(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can view history.", ephemeral=True)
            return
        await interaction.response.send_message(embed=self.bot.history_embed(), ephemeral=True)


# --- Main bot class ----------------------------------------------------------


class AnnouncementBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data_path = os.getenv("ANNOUNCEMENT_DATA_PATH") or "./data"
        os.makedirs(data_path, exist_ok=True)
        self.data_file = os.path.join(data_path, DATA_FILENAME)
        self.data = self.load()
        self.dispatch_task = None

        # Seed the target channel from .env the first time we run.
        env_channel = os.getenv("ANNOUNCEMENT_CHANNEL_ID")
        if not self.data.get("channel_id") and env_channel and env_channel.strip().isdigit():
            self.data["channel_id"] = int(env_channel.strip())

    # -- persistence ---------------------------------------------------------

    def load(self) -> Dict:
        if not os.path.exists(self.data_file):
            return _blank_data()
        try:
            with open(self.data_file, "r", encoding="utf-8") as handle:
                content = json.load(handle)
        except (json.JSONDecodeError, OSError) as exc:
            print("AnnouncementBot: could not read {}: {}".format(self.data_file, exc))
            return _blank_data()

        if not isinstance(content, dict):
            return _blank_data()
        merged = _blank_data()
        merged.update(content)
        merged["announcements"] = [a for a in content.get("announcements", []) if isinstance(a, dict)]
        return merged

    def save(self):
        with open(self.data_file, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=4, default=str)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def is_admin(user) -> bool:
        perms = getattr(user, "guild_permissions", None)
        return bool(perms and perms.administrator)

    async def resolve_channel(self, channel_id):
        if not channel_id:
            return None
        channel = self.get_channel(int(channel_id))
        if channel is None:
            try:
                channel = await self.fetch_channel(int(channel_id))
            except Exception:
                return None
        return channel

    def find(self, ann_id: str) -> Optional[Dict]:
        for entry in self.data["announcements"]:
            if entry.get("id") == ann_id:
                return entry
        return None

    def add_announcement(
        self,
        title: str,
        body: str,
        send_at: str,
        author,
        channel_id: int,
        ping: bool = False,
    ) -> Dict:
        entry = {
            "id": uuid.uuid4().hex[:8],
            "title": title,
            "body": body,
            "send_at": send_at,
            "created_at": sched.to_iso(sched.current_time()),
            "created_by": getattr(author, "id", None),
            "created_by_name": str(author),
            "channel_id": int(channel_id) if channel_id else None,
            "channel_name": self.data.get("channel_name"),
            "ping": bool(ping),
            "status": "pending",
            "message_id": None,
            "sent_at": None,
            "error": None,
        }
        self.data["announcements"].append(entry)
        self.save()
        return entry

    def cancel_announcement(self, ann_id: str, author=None) -> bool:
        entry = self.find(ann_id)
        if not entry or entry.get("status") != "pending":
            return False
        entry["status"] = "cancelled"
        entry["cancelled_at"] = sched.to_iso(sched.current_time())
        entry["cancelled_by_name"] = str(author) if author else None
        self.save()
        return True

    # -- rendering -----------------------------------------------------------

    def build_embed(self, entry: Dict) -> discord.Embed:
        embed = discord.Embed(
            title=entry["title"],
            description=entry["body"],
            color=EMBED_COLOR,
        )
        embed.set_footer(text=bot_config.ANNOUNCEMENT_BOT_FOOTER)
        embed.timestamp = sched.current_time()
        return embed

    def preview_embed(self, payload: Dict, send_at: datetime) -> discord.Embed:
        embed = discord.Embed(
            title=payload["title"],
            description=payload["body"],
            color=PANEL_COLOR,
        )
        embed.add_field(
            name="Sends",
            value="{} ({})\nParsed from `{}`".format(
                sched.format_with_zone(send_at), sched.humanize(send_at), payload["raw_when"]
            ),
            inline=False,
        )
        embed.add_field(name="Channel", value=_channel_mention(self.data.get("channel_id")), inline=False)
        embed.set_footer(text="Confirm below. This preview is private to you.")
        return embed

    def status_embed(self, entry: Dict, show_body: bool = True) -> discord.Embed:
        colors = {
            "pending": PANEL_COLOR,
            "sent": 0x2ECC71,
            "cancelled": 0x95A5A6,
            "failed": ERROR_COLOR,
        }
        embed = discord.Embed(
            title=entry.get("title", "Announcement"),
            description=entry.get("body") if show_body else None,
            color=colors.get(entry.get("status"), PANEL_COLOR),
        )
        send_at = sched.from_iso(entry["send_at"]) if entry.get("send_at") else None
        embed.add_field(
            name="Status",
            value=str(entry.get("status", "unknown")).upper(),
            inline=True,
        )
        embed.add_field(
            name="Scheduled for",
            value=sched.format_with_zone(send_at) if send_at else "unknown",
            inline=True,
        )
        embed.add_field(
            name="Channel",
            value=_channel_mention(entry.get("channel_id")),
            inline=True,
        )
        extra = []
        if entry.get("ping"):
            extra.append("Pings @everyone")
        if entry.get("created_by_name"):
            extra.append("Created by {}".format(entry["created_by_name"]))
        if entry.get("sent_at"):
            extra.append("Actually sent {}".format(sched.format_with_zone(sched.from_iso(entry["sent_at"]))))
        if entry.get("error"):
            extra.append("Error: {}".format(entry["error"]))
        if extra:
            embed.add_field(name="Details", value="\n".join(extra), inline=False)
        embed.set_footer(text="ID {}".format(entry.get("id", "?")))
        return embed

    def history_embed(self) -> discord.Embed:
        sent = [a for a in self.data["announcements"] if a.get("status") in ("sent", "failed")]
        sent.sort(key=lambda a: a.get("sent_at") or "", reverse=True)
        embed = discord.Embed(title="Announcement History", color=PANEL_COLOR)
        if not sent:
            embed.description = "Nothing has been sent yet."
            return embed
        lines = []
        for entry in sent[:15]:
            stamp = sched.format_local(sched.from_iso(entry["sent_at"])) if entry.get("sent_at") else "?"
            mark = "sent" if entry["status"] == "sent" else "FAILED"
            lines.append("[{}] {} - {}".format(mark, stamp, entry.get("title", "?")))
        embed.description = "\n".join(lines)
        embed.set_footer(text="Showing the last {} of {}".format(min(15, len(sent)), len(sent)))
        return embed

    def panel_embed(self) -> discord.Embed:
        pending = sched.pending_announcements(self.data["announcements"])
        channel_id = self.data.get("channel_id")

        embed = discord.Embed(
            title="{} (Announcement Bot)".format(bot_config.ANNOUNCEMENT_BOT_NICKNAME),
            description=(
                "Writes and schedules announcements.\n\n"
                "**Usage:**\n"
                "**New Announcement** - asks for a title, a send time, then the announcement text.\n"
                "**Set Announcement Channel** - picks where announcements are posted.\n"
                "**Scheduled** - review, send early, or cancel queued posts.\n"
                "**History** - what already went out."
            ),
            color=PANEL_COLOR,
        )
        embed.add_field(name="Posting to", value=_channel_mention(channel_id), inline=True)
        embed.add_field(name="Queued", value=str(len(pending)), inline=True)
        embed.add_field(name="Time zone", value=sched.tz_label(), inline=True)

        if not channel_id:
            embed.add_field(
                name="Action needed",
                value="No channel set. Press **Set Announcement Channel** before scheduling anything.",
                inline=False,
            )
        elif pending:
            lines = []
            for entry in pending[:5]:
                when = sched.from_iso(entry["send_at"])
                lines.append("- `{}` {} ({})".format(entry["id"], sched.format_local(when), sched.humanize(when)))
            if len(pending) > 5:
                lines.append("... and {} more".format(len(pending) - 5))
            embed.add_field(name="Next up", value="\n".join(lines), inline=False)

        embed.set_footer(text=bot_config.ANNOUNCEMENT_BOT_FOOTER)
        return embed

    async def update_panel(self):
        chan_id = self.data.get("admin_channel_id")
        msg_id = self.data.get("admin_message_id")
        if not chan_id or not msg_id:
            return
        try:
            channel = await self.resolve_channel(chan_id)
            if channel is None:
                return
            message = await channel.fetch_message(int(msg_id))
            await message.edit(embed=self.panel_embed(), view=AnnouncementAdminView(self))
        except discord.NotFound:
            self.data["admin_message_id"] = None
            self.save()
        except Exception as exc:
            print("AnnouncementBot: panel update failed: {}".format(exc))

    # -- delivery ------------------------------------------------------------

    async def deliver(self, entry: Dict) -> bool:
        channel = await self.resolve_channel(entry.get("channel_id") or self.data.get("channel_id"))
        if channel is None:
            entry["status"] = "failed"
            entry["error"] = "Target channel could not be resolved"
            self.save()
            await self.notify_admin("Could not post **{}**: target channel missing.".format(entry.get("title")))
            return False

        content = "@everyone" if entry.get("ping") else None
        try:
            message = await channel.send(content=content, embed=self.build_embed(entry))
        except discord.Forbidden:
            entry["status"] = "failed"
            entry["error"] = "Missing permission to post in {}".format(getattr(channel, "name", channel.id))
        except discord.HTTPException as exc:
            entry["status"] = "failed"
            entry["error"] = "{}".format(exc)
        else:
            entry["status"] = "sent"
            entry["message_id"] = message.id
            entry["sent_at"] = sched.to_iso(sched.current_time())
            entry["error"] = None

        self.save()
        if entry["status"] == "sent":
            print("AnnouncementBot: sent '{}' to {}".format(entry.get("title"), getattr(channel, "name", channel.id)))
        else:
            print("AnnouncementBot: failed '{}': {}".format(entry.get("title"), entry.get("error")))
            await self.notify_admin(
                "Announcement **{}** failed: {}".format(entry.get("title"), entry.get("error"))
            )
        return entry["status"] == "sent"

    async def notify_admin(self, text: str):
        chan_id = self.data.get("admin_channel_id") or os.getenv("ADMIN_CHANNEL_ID")
        if not chan_id:
            return
        channel = await self.resolve_channel(chan_id)
        if channel is None:
            return
        try:
            await channel.send(text)
        except Exception:
            pass

    async def dispatch_due(self):
        due = sched.due_announcements(self.data["announcements"])
        if not due:
            return 0
        for entry in due:
            await self.deliver(entry)
        await self.update_panel()
        return len(due)

    # -- lifecycle -----------------------------------------------------------

    async def setup_hook(self):
        # Persistent so the panel buttons keep working after a restart.
        self.add_view(AnnouncementAdminView(self))
        self.dispatch_task = self.check_announcements.start()

    @tasks.loop(seconds=20)
    async def check_announcements(self):
        try:
            await self.dispatch_due()
        except Exception as exc:
            print("AnnouncementBot: dispatch loop error: {}".format(exc))

    @check_announcements.before_loop
    async def before_check_announcements(self):
        await self.wait_until_ready()

    async def on_ready(self):
        print("{} logged in as {} (ID: {})".format(
            bot_config.ANNOUNCEMENT_BOT_NICKNAME, self.user, self.user.id
        ))
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.ANNOUNCEMENT_BOT_NICKNAME)
            except Exception as exc:
                print("Nickname change failed in {}: {}".format(guild.name, exc))

        pending = sched.pending_announcements(self.data["announcements"])
        if pending:
            print("AnnouncementBot: {} announcement(s) queued.".format(len(pending)))
        await self.update_panel()

    # -- commands ------------------------------------------------------------

    async def on_message(self, message):
        if message.author == self.user or not message.content:
            return

        content = message.content.strip()

        # Universal admin panel registration
        if content.startswith("!admin_setup"):
            if not self.is_admin(message.author):
                return
            admin_channel_id = os.getenv("ADMIN_CHANNEL_ID")
            if admin_channel_id and str(message.channel.id) != str(admin_channel_id):
                return

            # The other bots purge this channel on setup; wait our turn so we are
            # not posting into a purge that has not run yet.
            await asyncio.sleep(3)

            try:
                panel = await message.channel.send(embed=self.panel_embed(), view=AnnouncementAdminView(self))
            except Exception as exc:
                print("AnnouncementBot failed to post admin panel: {}".format(exc))
                return

            self.data["admin_channel_id"] = message.channel.id
            self.data["admin_message_id"] = panel.id
            self.save()
            return

        if content.startswith("!announce"):
            if not self.is_admin(message.author):
                await message.channel.send("You need Administrator permissions to use this command.")
                return

            argument = content[len("!announce"):].strip()

            # !announce            -> open the compose modal
            if argument == "":
                await message.channel.send(
                    "Use the button below to write an announcement:",
                    view=_ModalLauncherView(),
                )
                return

            if argument.startswith("list"):
                entries = sched.pending_announcements(self.data["announcements"])
                if not entries:
                    await message.channel.send("Nothing scheduled.")
                    return
                lines = []
                for entry in entries[:15]:
                    when = sched.from_iso(entry["send_at"])
                    lines.append(
                        "- `{}` {} ({}) - {}".format(entry["id"], sched.format_local(when), sched.humanize(when), entry["title"])
                    )
                embed = discord.Embed(
                    title="Scheduled Announcements",
                    description="\n".join(lines),
                    color=PANEL_COLOR,
                )
                embed.set_footer(text="Cancel with !announce cancel <id>")
                await message.channel.send(embed=embed)
                return

            if argument.startswith("channel"):
                self.data["channel_id"] = message.channel.id
                self.data["channel_name"] = getattr(message.channel, "name", str(message.channel.id))
                self.save()
                await message.channel.send("Announcements will post to {}.".format(message.channel.mention))
                await self.update_panel()
                return

            if argument.startswith("cancel"):
                parts = argument.split()
                if len(parts) < 2:
                    await message.channel.send("Usage: `!announce cancel <id>`")
                    return
                ann_id = parts[1].strip().strip("`")
                if self.cancel_announcement(ann_id, message.author):
                    await message.channel.send("Cancelled `{}`.".format(ann_id))
                    await self.update_panel()
                else:
                    await message.channel.send("No pending announcement with id `{}`.".format(ann_id))
                return

            if argument.startswith("panel"):
                if not self.is_admin(message.author):
                    return
                panel = await message.channel.send(embed=self.panel_embed(), view=AnnouncementAdminView(self))
                self.data["admin_channel_id"] = message.channel.id
                self.data["admin_message_id"] = panel.id
                self.save()
                return

            await message.channel.send(
                "Unknown option. Use `!announce` to compose, `!announce list`, "
                "`!announce channel`, or `!announce cancel <id>`."
            )


class _ModalLauncherView(ui.View):
    """One-shot button that opens the compose modal (used by the !announce command)."""

    def __init__(self):
        super().__init__(timeout=300)

    @ui.button(label="New Announcement", style=discord.ButtonStyle.success)
    async def open_modal(self, interaction: discord.Interaction, button: ui.Button):
        bot: "AnnouncementBot" = interaction.client
        if not bot.is_admin(interaction.user):
            await interaction.response.send_message("Only Admins can write announcements.", ephemeral=True)
            return
        await interaction.response.send_modal(AnnouncementModal())
