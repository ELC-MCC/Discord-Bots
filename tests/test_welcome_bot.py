"""Tests for the welcome bot's join handling.

Runs against the real WelcomeBot with fakes, no Discord connection needed:

    python tests/test_welcome_bot.py
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import discord

import bot_config
from bots.welcome_bot import WelcomeBot

WELCOME_ENV_KEYS = [
    "WELCOME_CHANNEL_ID",
    "GENERAL_CHANNEL_ID",
    "INTRODUCTIONS_CHANNEL_ID",
    "MAKER_GENERAL_CHANNEL_ID",
]

GOOD_ENV = {
    "WELCOME_CHANNEL_ID": "111111111111111111",
    "GENERAL_CHANNEL_ID": "222222222222222222",
    "INTRODUCTIONS_CHANNEL_ID": "333333333333333333",
    "MAKER_GENERAL_CHANNEL_ID": "444444444444444444",
}

WELCOME_CHANNEL_ID = int(GOOD_ENV["WELCOME_CHANNEL_ID"])


class FakeAvatar:
    url = "https://cdn.discordapp.com/embed/avatars/0.png"


class FakeChannel:
    def __init__(self, channel_id, name="new-people"):
        self.id = channel_id
        self.name = name
        self.mention = "<#{}>".format(channel_id)
        self.sent = []

    async def send(self, content=None, embed=None, **kwargs):
        self.sent.append({"content": content, "embed": embed})


class FakeGuild:
    def __init__(self, channels, name="ELC"):
        self.name = name
        self._channels = {c.id: c for c in channels}
        self.text_channels = list(channels)
        self.me = _FakeMe()

    def get_channel(self, channel_id):
        return self._channels.get(channel_id)


class _FakeMe:
    def __init__(self):
        self.id = 1

    async def edit(self, **kwargs):
        return None


class FakeMember:
    def __init__(self, guild, member_id=555, name="newbie", pending=False):
        self.guild = guild
        self.id = member_id
        self.name = name
        self.display_name = name
        self.mention = "<@{}>".format(member_id)
        self.pending = pending
        self.avatar = None
        self.default_avatar = FakeAvatar()


class WelcomeBotTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in WELCOME_ENV_KEYS}
        for k, v in GOOD_ENV.items():
            os.environ[k] = v
        self.channel = FakeChannel(WELCOME_CHANNEL_ID)
        self.guild = FakeGuild([self.channel])
        self.bot = WelcomeBot(intents=discord.Intents.none())

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def member(self, member_id=555, pending=False):
        return FakeMember(self.guild, member_id=member_id, pending=pending)

    def welcomes(self):
        return [m for m in self.channel.sent if m["embed"] is not None]


class HappyPathTests(WelcomeBotTestCase):
    async def test_normal_join_posts_a_welcome(self):
        member = self.member()
        await self.bot.on_member_join(member)
        self.assertEqual(len(self.welcomes()), 1)

    async def test_welcome_uses_display_name_not_id(self):
        member = self.member()
        await self.bot.on_member_join(member)
        embed = self.welcomes()[0]["embed"]
        self.assertIn(member.display_name, embed.description)
        self.assertNotIn(str(member.id), embed.description)

    async def test_welcome_uses_a_pun_title(self):
        member = self.member()
        await self.bot.on_member_join(member)
        self.assertIn(self.welcomes()[0]["embed"].title, bot_config.WELCOME_PUNS)

    async def test_pending_member_is_deferred_then_welcomed_on_screen_pass(self):
        before = self.member(pending=True)
        await self.bot.on_member_join(before)
        self.assertEqual(self.welcomes(), [], "should wait while pending")

        after = self.member()
        await self.bot.on_member_update(before, after)
        self.assertEqual(len(self.welcomes()), 1, "should welcome once screening passes")

    async def test_duplicate_events_only_welcome_once(self):
        member = self.member()
        await self.bot.on_member_join(member)
        await self.bot.on_member_update(self.member(pending=True), member)
        self.assertEqual(len(self.welcomes()), 1, "debounce should suppress the echo")


class MissingChannelConfigTests(WelcomeBotTestCase):
    """A blank or unknown WELCOME_CHANNEL_ID must never stop the welcome.

    .env.example ships these keys empty, so a half configured server has
    WELCOME_CHANNEL_ID= present but blank. os.getenv returns '' (not the default)
    for a blank value, and the old code called int('') directly.
    """

    async def test_blank_channel_id_still_welcomes_via_name_fallback(self):
        os.environ["WELCOME_CHANNEL_ID"] = ""
        member = self.member()
        await self.bot.on_member_join(member)
        self.assertEqual(len(self.welcomes()), 1, "blank id must fall back to the name search")

    async def test_blank_channel_id_does_not_raise(self):
        os.environ["WELCOME_CHANNEL_ID"] = "   "
        member = self.member()
        try:
            await self.bot.on_member_join(member)
        except Exception as exc:  # noqa: BLE001 - that is exactly what we are asserting
            self.fail("blank WELCOME_CHANNEL_ID raised {}: {}".format(type(exc).__name__, exc))

    async def test_non_numeric_channel_id_does_not_raise(self):
        os.environ["WELCOME_CHANNEL_ID"] = "#new-people"
        member = self.member()
        try:
            await self.bot.on_member_join(member)
        except Exception as exc:  # noqa: BLE001
            self.fail("non-numeric WELCOME_CHANNEL_ID raised {}: {}".format(type(exc).__name__, exc))

    async def test_unknown_channel_id_falls_back_to_name(self):
        os.environ["WELCOME_CHANNEL_ID"] = "999999999999999999"
        member = self.member()
        await self.bot.on_member_join(member)
        self.assertEqual(len(self.welcomes()), 1, "unknown id should fall back to name search")

    async def test_no_channel_anywhere_logs_and_does_not_raise(self):
        os.environ["WELCOME_CHANNEL_ID"] = ""
        empty_guild = FakeGuild([])
        member = FakeMember(empty_guild)
        try:
            await self.bot.on_member_join(member)
        except Exception as exc:  # noqa: BLE001
            self.fail("missing channels raised {}: {}".format(type(exc).__name__, exc))


class WhereToStartFieldTests(WelcomeBotTestCase):
    async def test_field_lists_all_configured_channels(self):
        await self.bot.on_member_join(self.member())
        embed = self.welcomes()[0]["embed"]
        field = next(f for f in embed.fields if f.name == "Where to Start")
        self.assertIn("<#{}>".format(GOOD_ENV["GENERAL_CHANNEL_ID"]), field.value)
        self.assertIn("<#{}>".format(GOOD_ENV["INTRODUCTIONS_CHANNEL_ID"]), field.value)
        self.assertIn("<#{}>".format(GOOD_ENV["MAKER_GENERAL_CHANNEL_ID"]), field.value)

    async def test_unset_channels_do_not_render_literal_none(self):
        for key in ("GENERAL_CHANNEL_ID", "INTRODUCTIONS_CHANNEL_ID", "MAKER_GENERAL_CHANNEL_ID"):
            os.environ.pop(key, None)
        await self.bot.on_member_join(self.member())
        embed = self.welcomes()[0]["embed"]
        blob = "\n".join(f.value for f in embed.fields)
        self.assertNotIn("<#None>", blob, "unset channel ids render as a broken mention")

    async def test_field_omitted_when_nothing_configured(self):
        for key in ("GENERAL_CHANNEL_ID", "INTRODUCTIONS_CHANNEL_ID", "MAKER_GENERAL_CHANNEL_ID"):
            os.environ.pop(key, None)
        await self.bot.on_member_join(self.member())
        embed = self.welcomes()[0]["embed"]
        self.assertEqual([f.name for f in embed.fields], [], "empty field looks broken in Discord")


class DebounceStateTests(WelcomeBotTestCase):
    async def test_memory_does_not_grow_without_bound(self):
        for i in range(500):
            await self.bot.send_welcome(self.member(member_id=1000 + i))
        self.assertLessEqual(
            len(self.bot.last_welcome_time),
            500,
            "sanity: dict holds one entry per member welcomed",
        )
        self.assertLessEqual(
            len(self.bot.last_welcome_time),
            200,
            "unbounded growth: last_welcome_time should be pruned",
        )

    async def test_failed_send_can_be_retried(self):
        class ExplodingChannel(FakeChannel):
            async def send(self, content=None, embed=None, **kwargs):
                raise discord.HTTPException(_FakeResponse(), "boom")

        broken = ExplodingChannel(WELCOME_CHANNEL_ID)
        self.guild._channels[WELCOME_CHANNEL_ID] = broken
        member = self.member()
        await self.bot.on_member_join(member)  # fails to send

        self.guild._channels[WELCOME_CHANNEL_ID] = self.channel
        await self.bot.on_member_update(self.member(pending=True), member)
        self.assertEqual(
            len(self.welcomes()), 1,
            "a failed send should not poison the debounce and block the retry",
        )


class _FakeResponse:
    status = 500
    reason = "Server Error"


if __name__ == "__main__":
    unittest.main(verbosity=2)
