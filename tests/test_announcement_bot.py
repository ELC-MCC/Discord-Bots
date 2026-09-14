"""Smoke tests for the announcement bot.

Exercises the real bot class, every view, the JSON store and the due-dispatch
path against a fake channel, so it catches discord.py API mistakes and data
bugs without needing a live token or a network connection.

    python tests/test_announcement_bot.py
"""

import asyncio
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import discord

from bots.announcement_bot import (
    AnnouncementAdminView,
    AnnouncementBot,
    AnnouncementChannelSelect,
    AnnouncementModal,
    ConfirmAnnouncementView,
    ManageAnnouncementsView,
    _ModalLauncherView,
)
from utils import announcement_scheduler as sched


# --- Fakes -------------------------------------------------------------------


class FakeAuthor:
    def __init__(self, name="admin", user_id=99):
        self.name = name
        self.id = user_id
        self.guild_permissions = discord.Permissions(administrator=True)

    def __str__(self):
        return self.name


class FakeMessageRef:
    def __init__(self, message_id=555):
        self.id = message_id


class FakeChannel:
    def __init__(self, channel_id=1234, name="announcements", fail=None, message_id=555):
        self.id = channel_id
        self.name = name
        self.mention = "<#{}>".format(channel_id)
        self.sent = []
        self._fail = fail
        self._message_id = message_id

    async def send(self, content=None, embed=None, **kwargs):
        if self._fail is not None:
            raise self._fail
        self.sent.append({"content": content, "embed": embed})
        return FakeMessageRef(self._message_id)

    async def fetch_message(self, message_id):
        raise discord.NotFound(_FakeResponse(), "no message")


class _FakeResponse:
    status = 404
    reason = "Not Found"


# --- Helpers -----------------------------------------------------------------


def make_bot(data_dir):
    os.environ["ANNOUNCEMENT_DATA_PATH"] = data_dir
    os.environ.pop("ANNOUNCEMENT_CHANNEL_ID", None)
    os.environ.pop("ANNOUNCEMENT_TIMEZONE", None)
    sched.reset_cache()
    return AnnouncementBot(intents=discord.Intents.none())


class BotTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="announce-test-")
        self.bot = make_bot(self.tmp)
        self.author = FakeAuthor()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("ANNOUNCEMENT_DATA_PATH", None)

    def store_path(self):
        return os.path.join(self.tmp, "announcements.json")


# --- Component construction --------------------------------------------------


class ComponentTests(BotTestCase):
    def test_every_view_builds(self):
        payload = {"title": "T", "body": "B", "raw_when": "30m", "send_at": sched.to_iso(sched.current_time())}
        for view in (
            AnnouncementAdminView(self.bot),
            AnnouncementChannelSelect(self.bot),
            ConfirmAnnouncementView(self.bot, payload),
            ManageAnnouncementsView(self.bot, []),
            _ModalLauncherView(),
        ):
            self.assertIsInstance(view, discord.ui.View)

    def test_modal_builds(self):
        self.assertIsInstance(AnnouncementModal(), discord.ui.Modal)

    def test_modal_asks_the_three_questions(self):
        modal = AnnouncementModal()
        inputs = [c for c in modal.children if isinstance(c, discord.ui.TextInput)]
        self.assertEqual(len(inputs), 3, "expected title / when / announcement")
        self.assertEqual([i.label for i in inputs], ["Title", "When to send", "Announcement"])
        self.assertEqual(inputs[1].style, discord.TextStyle.short)
        self.assertEqual(inputs[2].style, discord.TextStyle.paragraph, "announcement body must be multiline")

    def test_panel_button_ids_are_stable(self):
        view = AnnouncementAdminView(self.bot)
        custom_ids = {item.custom_id for item in view.children}
        self.assertEqual(
            custom_ids,
            {
                "announce_admin_new",
                "announce_admin_channel",
                "announce_admin_list",
                "announce_admin_history",
            },
        )

    def test_panel_embed_warns_when_no_channel(self):
        embed = self.bot.panel_embed()
        field_names = [f.name for f in embed.fields]
        self.assertIn("Action needed", field_names)

    def test_panel_embed_lists_next_up(self):
        self.bot.data["channel_id"] = 42
        self.bot.data["channel_name"] = "announcements"
        self.bot.add_announcement(
            title="Hi", body="There", send_at=sched.to_iso(sched.current_time() + timedelta(hours=3)),
            author=self.author, channel_id=42,
        )
        embed = self.bot.panel_embed()
        self.assertIn("Next up", [f.name for f in embed.fields])
        self.assertIn("Queued", [f.name for f in embed.fields])


# --- Storage -----------------------------------------------------------------


class StorageTests(BotTestCase):
    def test_add_persists_and_reloads(self):
        entry = self.bot.add_announcement(
            title="Winter break",
            body="We are closed.",
            send_at=sched.to_iso(sched.current_time() + timedelta(hours=1)),
            author=self.author,
            channel_id=777,
        )
        self.assertTrue(os.path.exists(self.store_path()))

        with open(self.store_path(), "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        self.assertEqual(len(raw["announcements"]), 1)
        self.assertEqual(raw["announcements"][0]["title"], "Winter break")

        reloaded = make_bot(self.tmp)
        self.assertEqual(len(reloaded.data["announcements"]), 1)
        self.assertEqual(reloaded.data["announcements"][0]["id"], entry["id"])
        self.assertEqual(reloaded.find(entry["id"])["body"], "We are closed.")

    def test_cancel_marks_status(self):
        entry = self.bot.add_announcement(
            title="X", body="Y", send_at=sched.to_iso(sched.current_time() + timedelta(hours=2)),
            author=self.author, channel_id=777,
        )
        self.assertTrue(self.bot.cancel_announcement(entry["id"], self.author))
        self.assertEqual(self.bot.find(entry["id"])["status"], "cancelled")
        # Cancelling twice must not report success again.
        self.assertFalse(self.bot.cancel_announcement(entry["id"], self.author))

    def test_corrupt_store_does_not_crash(self):
        with open(self.store_path(), "w", encoding="utf-8") as handle:
            handle.write("{not json")
        recovered = make_bot(self.tmp)
        self.assertEqual(recovered.data["announcements"], [])

    def test_env_channel_seeds_target(self):
        os.environ["ANNOUNCEMENT_CHANNEL_ID"] = "424242"
        bot = AnnouncementBot(intents=discord.Intents.none())
        self.assertEqual(bot.data["channel_id"], 424242)


# --- Dispatch ----------------------------------------------------------------


class DispatchTests(BotTestCase):
    def test_pending_future_announcement_is_not_sent(self):
        channel = FakeChannel()
        self.bot.resolve_channel = _resolver(channel)
        self.bot.add_announcement(
            title="Later", body="body",
            send_at=sched.to_iso(sched.current_time() + timedelta(hours=1)),
            author=self.author, channel_id=channel.id,
        )
        sent = asyncio.run(self.bot.dispatch_due())
        self.assertEqual(sent, 0)
        self.assertEqual(channel.sent, [])

    def test_due_announcement_is_sent_and_recorded(self):
        channel = FakeChannel()
        self.bot.resolve_channel = _resolver(channel)
        entry = self.bot.add_announcement(
            title="Fire drill", body="Please evacuate.",
            send_at=sched.to_iso(sched.current_time() - timedelta(minutes=1)),
            author=self.author, channel_id=channel.id,
        )

        sent = asyncio.run(self.bot.dispatch_due())

        self.assertEqual(sent, 1)
        self.assertEqual(len(channel.sent), 1)
        embed = channel.sent[0]["embed"]
        self.assertEqual(embed.title, "Fire drill")
        self.assertEqual(embed.description, "Please evacuate.")
        self.assertIsNone(channel.sent[0]["content"], "should not ping by default")

        self.assertEqual(entry["status"], "sent")
        self.assertEqual(entry["message_id"], 555)
        self.assertIsNotNone(entry["sent_at"])

        # Must not fire a second time.
        self.assertEqual(asyncio.run(self.bot.dispatch_due()), 0)
        self.assertEqual(len(channel.sent), 1)

        # And the result must survive a reload.
        reloaded = make_bot(self.tmp)
        self.assertEqual(reloaded.find(entry["id"])["status"], "sent")

    def test_ping_flag_adds_everyone_content(self):
        channel = FakeChannel()
        self.bot.resolve_channel = _resolver(channel)
        self.bot.add_announcement(
            title="Urgent", body="Now", send_at=sched.to_iso(sched.current_time() - timedelta(seconds=5)),
            author=self.author, channel_id=channel.id, ping=True,
        )
        asyncio.run(self.bot.dispatch_due())
        self.assertEqual(channel.sent[0]["content"], "@everyone")

    def test_forbidden_marks_failed_with_reason(self):
        channel = FakeChannel(fail=discord.Forbidden(_FakeResponse(), "missing perms"))
        self.bot.resolve_channel = _resolver(channel)
        self.bot.data["admin_channel_id"] = None
        entry = self.bot.add_announcement(
            title="Nope", body="body", send_at=sched.to_iso(sched.current_time() - timedelta(seconds=5)),
            author=self.author, channel_id=channel.id,
        )
        asyncio.run(self.bot.dispatch_due())
        self.assertEqual(entry["status"], "failed")
        self.assertIn("permission", entry["error"].lower())

    def test_unresolvable_channel_marks_failed(self):
        async def no_channel(channel_id):
            return None

        self.bot.resolve_channel = no_channel
        entry = self.bot.add_announcement(
            title="Lost", body="body", send_at=sched.to_iso(sched.current_time() - timedelta(seconds=5)),
            author=self.author, channel_id=12345,
        )
        self.assertFalse(asyncio.run(self.bot.deliver(entry)))
        self.assertEqual(entry["status"], "failed")

    def test_cancelled_announcement_never_sends(self):
        channel = FakeChannel()
        self.bot.resolve_channel = _resolver(channel)
        entry = self.bot.add_announcement(
            title="Cancelled", body="body",
            send_at=sched.to_iso(sched.current_time() - timedelta(minutes=5)),
            author=self.author, channel_id=channel.id,
        )
        self.bot.cancel_announcement(entry["id"], self.author)
        self.assertEqual(asyncio.run(self.bot.dispatch_due()), 0)
        self.assertEqual(channel.sent, [])

    def test_missed_announcement_still_fires_after_restart(self):
        # Announcement was due while the bot was down.
        channel = FakeChannel()
        self.bot.resolve_channel = _resolver(channel)
        self.bot.add_announcement(
            title="Missed", body="late", send_at=sched.to_iso(sched.current_time() - timedelta(hours=6)),
            author=self.author, channel_id=channel.id,
        )
        restarted = make_bot(self.tmp)
        restarted.resolve_channel = _resolver(channel)
        self.assertEqual(asyncio.run(restarted.dispatch_due()), 1)
        self.assertEqual(channel.sent[0]["embed"].title, "Missed")

    def test_deliver_falls_back_to_panel_channel(self):
        channel = FakeChannel(channel_id=8888)
        self.bot.resolve_channel = _resolver(channel)
        self.bot.data["channel_id"] = 8888
        entry = self.bot.add_announcement(
            title="Fallback", body="body",
            send_at=sched.to_iso(sched.current_time() - timedelta(seconds=5)),
            author=self.author, channel_id=None,
        )
        self.assertTrue(asyncio.run(self.bot.deliver(entry)))
        self.assertEqual(len(channel.sent), 1)


class HistoryTests(BotTestCase):
    def test_history_empty(self):
        embed = self.bot.history_embed()
        self.assertIn("Nothing has been sent", embed.description)

    def test_history_lists_sent(self):
        channel = FakeChannel()
        self.bot.resolve_channel = _resolver(channel)
        self.bot.add_announcement(
            title="Done", body="b", send_at=sched.to_iso(sched.current_time() - timedelta(seconds=5)),
            author=self.author, channel_id=channel.id,
        )
        asyncio.run(self.bot.dispatch_due())
        embed = self.bot.history_embed()
        self.assertIn("Done", embed.description)
        self.assertIn("sent", embed.description)

    def test_status_embed_renders_for_every_state(self):
        for status in ("pending", "sent", "failed", "cancelled"):
            entry = {
                "id": "abcd1234", "title": "T", "body": "B", "status": status,
                "send_at": sched.to_iso(sched.current_time()),
                "channel_id": 1, "sent_at": None, "error": None, "ping": True,
                "created_by_name": "admin",
            }
            embed = self.bot.status_embed(entry)
            self.assertEqual(embed.title, "T")


def _resolver(channel):
    async def resolve(channel_id):
        return channel
    return resolve


# --- End to end: the admin's actual click path -------------------------------


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, content=None, embed=None, view=None, ephemeral=False, **kwargs):
        self.messages.append({"content": content, "embed": embed, "view": view})

    async def edit_message(self, content=None, embed=None, view=None, **kwargs):
        self.messages.append({"content": content, "embed": embed, "view": view})

    async def defer(self, ephemeral=False, **kwargs):
        self.deferred = True


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content=None, embed=None, view=None, ephemeral=False, **kwargs):
        self.messages.append({"content": content, "embed": embed, "view": view})


class FakeGuild:
    def __init__(self):
        self.me = FakeAuthor("The Herald", 1)


class FakeInteraction:
    def __init__(self, bot, user=None):
        self.client = bot
        self.user = user or FakeAuthor()
        self.guild = FakeGuild()
        self.response = FakeResponse()
        self.followup = FakeFollowup()


def set_modal_values(modal, title, when, body):
    inputs = [c for c in modal.children if isinstance(c, discord.ui.TextInput)]
    inputs[0]._value = title
    inputs[1]._value = when
    inputs[2]._value = body


def button_name(view, label):
    for item in view.children:
        if getattr(item, "label", None) == label:
            return item
    raise AssertionError("no button labelled {!r} in {}".format(label, [i.label for i in view.children]))


async def press(view, label, interaction):
    """Invoke a button the way discord.py does, tolerating either binding style."""
    item = button_name(view, label)
    callback = item.callback
    if len(inspect.signature(callback).parameters) >= 3:
        return await callback(view, interaction, item)
    return await callback(interaction)


class FlowTests(BotTestCase):
    def setUp(self):
        super().setUp()
        self.channel = FakeChannel(channel_id=4242)
        self.bot.resolve_channel = _resolver(self.channel)
        self.bot.data["channel_id"] = self.channel.id
        self.bot.data["channel_name"] = self.channel.name

    def compose(self, title, when, body):
        """Submit the modal and return the confirmation view it produces."""
        modal = AnnouncementModal()
        set_modal_values(modal, title, when, body)
        interaction = FakeInteraction(self.bot)
        asyncio.run(modal.on_submit(interaction))
        sent = interaction.response.messages
        self.assertEqual(len(sent), 1, "modal should answer exactly once")
        return sent[0]

    def test_modal_previews_before_committing(self):
        answer = self.compose("Spring cleanup", "2h", "Bring gloves.")
        self.assertIsInstance(answer["view"], ConfirmAnnouncementView)
        self.assertEqual(answer["embed"].title, "Spring cleanup")
        # Nothing should be queued until the admin confirms.
        self.assertEqual(self.bot.data["announcements"], [])

    def test_modal_rejects_bad_time_with_help(self):
        answer = self.compose("Title", "next tuesday-ish", "Body")
        self.assertIsNone(answer["embed"])
        self.assertIn("Could not understand", answer["content"])
        self.assertIn("30m", answer["content"], "should show accepted formats")
        self.assertEqual(self.bot.data["announcements"], [])

    def test_confirm_then_send_end_to_end(self):
        answer = self.compose("Fire drill", "in 5 minutes", "Please evacuate the building.")
        view = answer["view"]

        interaction = FakeInteraction(self.bot)
        asyncio.run(press(view, "Schedule", interaction))

        # Queued, not sent.
        stored = self.bot.data["announcements"]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["status"], "pending")
        self.assertEqual(stored[0]["channel_id"], self.channel.id)
        self.assertEqual(self.channel.sent, [], "must not send before the time arrives")
        self.assertIn("Scheduled", interaction.response.messages[-1]["content"])

        # Rewind it to simulate time passing, then let the loop dispatch.
        stored[0]["send_at"] = sched.to_iso(sched.current_time() - timedelta(seconds=1))
        self.bot.save()
        self.assertEqual(asyncio.run(self.bot.dispatch_due()), 1)

        self.assertEqual(len(self.channel.sent), 1)
        self.assertEqual(self.channel.sent[0]["embed"].title, "Fire drill")
        self.assertEqual(self.bot.data["announcements"][0]["status"], "sent")

    def test_schedule_with_ping_sets_flag(self):
        answer = self.compose("Urgent", "now", "Server is down.")
        asyncio.run(press(answer["view"], "Schedule + @everyone", FakeInteraction(self.bot)))
        self.assertTrue(self.bot.data["announcements"][0]["ping"])
        asyncio.run(self.bot.dispatch_due())
        self.assertEqual(self.channel.sent[0]["content"], "@everyone")

    def test_cancel_leaves_queue_empty(self):
        answer = self.compose("Never mind", "1h", "Body")
        asyncio.run(press(answer["view"], "Cancel", FakeInteraction(self.bot)))
        self.assertEqual(self.bot.data["announcements"], [])

    def test_refuses_to_schedule_without_a_channel(self):
        self.bot.data["channel_id"] = None
        answer = self.compose("Homeless", "1h", "Body")
        interaction = FakeInteraction(self.bot)
        asyncio.run(press(answer["view"], "Schedule", interaction))
        self.assertEqual(self.bot.data["announcements"], [])
        self.assertIn("Set Announcement Channel", interaction.response.messages[-1]["content"])

    def test_non_admin_cannot_schedule(self):
        plain = FakeAuthor("member")
        plain.guild_permissions = discord.Permissions.none()
        answer = self.compose("Sneaky", "1h", "Body")
        interaction = FakeInteraction(self.bot, user=plain)
        asyncio.run(press(answer["view"], "Schedule", interaction))
        self.assertEqual(self.bot.data["announcements"], [])
        self.assertIn("Admins", interaction.response.messages[-1]["content"])

    def test_send_now_delivers_immediately(self):
        answer = self.compose("Right now", "2h", "Immediate body")
        interaction = FakeInteraction(self.bot)
        asyncio.run(press(answer["view"], "Send Now", interaction))
        self.assertEqual(len(self.channel.sent), 1)
        self.assertEqual(self.channel.sent[0]["embed"].title, "Right now")
        self.assertEqual(self.bot.data["announcements"][0]["status"], "sent")

    def test_admin_panel_buttons_are_wired(self):
        view = AnnouncementAdminView(self.bot)
        self.assertEqual(
            sorted(i.label for i in view.children),
            ["History", "New Announcement", "Scheduled", "Set Announcement Channel"],
        )

    def test_scheduled_list_shows_queued_items(self):
        self.compose_and_schedule("One", "1h", "b")
        self.compose_and_schedule("Two", "2h", "b")
        view = AnnouncementAdminView(self.bot)
        interaction = FakeInteraction(self.bot)
        asyncio.run(press(view, "Scheduled", interaction))
        message = interaction.response.messages[-1]
        self.assertIsInstance(message["view"], ManageAnnouncementsView)
        self.assertIn("2 scheduled", message["content"])
        options = [o.label for o in message["view"].children[0].options]
        self.assertEqual(len(options), 2)

    def compose_and_schedule(self, title, when, body):
        answer = self.compose(title, when, body)
        asyncio.run(press(answer["view"], "Schedule", FakeInteraction(self.bot)))
        return self.bot.data["announcements"][-1]


if __name__ == "__main__":
    unittest.main(verbosity=2)
