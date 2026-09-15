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


class FakePermissions:
    def __init__(self, view_channel=True, send_messages=True, embed_links=True):
        self.view_channel = view_channel
        self.send_messages = send_messages
        self.embed_links = embed_links


class FakeChannel:
    def __init__(self, channel_id, name="new-people", perms=None):
        self.id = channel_id
        self.name = name
        self.mention = "<#{}>".format(channel_id)
        self.sent = []
        self.perms = perms or FakePermissions()

    async def send(self, content=None, embed=None, **kwargs):
        self.sent.append({"content": content, "embed": embed})

    def permissions_for(self, member):
        return self.perms


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
        # members=True because diagnose() reports it as a problem when it is off.
        # Keep our own reference: client.intents hands back a COPY, so mutating that
        # is a no-op and the original is the object the client actually reads.
        self.intents = discord.Intents.default()
        self.intents.members = True
        self.intents.message_content = True
        self.bot = WelcomeBot(intents=self.intents)

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


# --- Diagnostics: the surfaces that exist to explain silence -----------------

EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0x2705, 0x2705),
    (0x274C, 0x274C),
    (0x26A0, 0x26A0),
)


def contains_emoji(text):
    for char in text:
        code = ord(char)
        if any(low <= code <= high for low, high in EMOJI_RANGES):
            return True
    return False


def embed_text(embed):
    parts = [embed.title or "", embed.description or "", embed.footer.text or ""]
    for field in embed.fields:
        parts.append(field.name or "")
        parts.append(field.value or "")
    return "\n".join(parts)


class DiagnoseTests(WelcomeBotTestCase):
    async def test_healthy_config_reports_no_problems(self):
        self.assertEqual(self.bot.diagnose(self.guild), [])

    async def test_reports_blank_channel_id(self):
        os.environ["WELCOME_CHANNEL_ID"] = ""
        problems = self.bot.diagnose(self.guild)
        self.assertTrue(any("WELCOME_CHANNEL_ID" in p for p in problems), problems)

    async def test_reports_nonexistent_channel_id(self):
        os.environ["WELCOME_CHANNEL_ID"] = "999999999999999999"
        problems = self.bot.diagnose(self.guild)
        self.assertTrue(any("does not exist in this server" in p for p in problems), problems)

    async def test_reports_missing_send_permission(self):
        self.channel.perms = FakePermissions(send_messages=False)
        problems = self.bot.diagnose(self.guild)
        self.assertTrue(any("Send Messages" in p for p in problems), problems)

    async def test_reports_missing_view_permission(self):
        self.channel.perms = FakePermissions(view_channel=False)
        problems = self.bot.diagnose(self.guild)
        self.assertTrue(any("View Channel" in p for p in problems), problems)

    async def test_reports_missing_embed_permission(self):
        self.channel.perms = FakePermissions(embed_links=False)
        problems = self.bot.diagnose(self.guild)
        self.assertTrue(any("Embed Links" in p for p in problems), problems)

    async def test_reports_no_channel_at_all(self):
        problems = self.bot.diagnose(FakeGuild([]))
        self.assertTrue(any("No welcome channel found" in p for p in problems), problems)

    async def test_reports_members_intent_off(self):
        self.intents.members = False
        problems = self.bot.diagnose(self.guild)
        self.assertTrue(any("Server Members intent" in p for p in problems), problems)

    async def test_resolve_returns_configured_channel(self):
        self.assertIs(self.bot.resolve_welcome_channel(self.guild), self.channel)

    async def test_resolve_falls_back_to_name(self):
        other = FakeChannel(4242, name="welcome")
        guild = FakeGuild([other])
        self.assertIs(self.bot.resolve_welcome_channel(guild), other)

    async def test_resolve_returns_none_when_nothing_matches(self):
        self.assertIsNone(self.bot.resolve_welcome_channel(FakeGuild([FakeChannel(1, name="random")])))


class DiagnosticEmbedTests(WelcomeBotTestCase):
    async def test_check_embed_says_ok_when_healthy(self):
        embed = self.bot.check_embed(self.guild)
        self.assertIn("No problems found", embed_text(embed))

    async def test_check_embed_lists_problems(self):
        os.environ["WELCOME_CHANNEL_ID"] = ""
        embed = self.bot.check_embed(self.guild)
        self.assertIn("WELCOME_CHANNEL_ID", embed_text(embed))

    async def test_check_embed_names_the_channel(self):
        embed = self.bot.check_embed(self.guild)
        self.assertIn(self.channel.mention, embed_text(embed))

    async def test_panel_embed_reports_health(self):
        embed = self.bot.panel_embed(self.guild)
        self.assertIn("OK", embed_text(embed))

    async def test_panel_embed_points_role_work_elsewhere(self):
        embed = self.bot.panel_embed(self.guild)
        names = [f.name for f in embed.fields]
        self.assertIn("Role handling", names)
        self.assertIn("Role Bot", embed_text(embed))

    async def test_panel_uses_configured_nickname(self):
        embed = self.bot.panel_embed(self.guild)
        self.assertIn(bot_config.WELCOME_BOT_NICKNAME, embed.title)

    async def test_diagnostics_contain_no_emoji(self):
        # Emoji were removed from the bot UIs on request; keep it that way.
        for embed in (self.bot.check_embed(self.guild), self.bot.panel_embed(self.guild)):
            self.assertFalse(
                contains_emoji(embed_text(embed)),
                "emoji found in: {}".format(embed_text(embed)),
            )

    async def test_diagnostics_contain_no_emoji_when_unhealthy(self):
        os.environ["WELCOME_CHANNEL_ID"] = ""
        self.channel.perms = FakePermissions(send_messages=False)
        for embed in (self.bot.check_embed(self.guild), self.bot.panel_embed(self.guild)):
            self.assertFalse(contains_emoji(embed_text(embed)))


class _FakeResponse:
    status = 500
    reason = "Server Error"


if __name__ == "__main__":
    unittest.main(verbosity=2)
