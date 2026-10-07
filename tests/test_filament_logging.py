import asyncio
import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)  # insert, not append

import discord
from bots.filament_bot import FilamentBot, LogUsageModal
from utils.filament_data_manager import FilamentDataManager


class FakeAuthor:
    def __init__(self, name="Connor", user_id=99):
        self.name = name
        self.id = user_id
        self.display_name = name
        self.guild_permissions = discord.Permissions(administrator=True)

    def __str__(self):
        return self.name


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.deferred = False

    async def send_message(self, content=None, embed=None, view=None, ephemeral=False, **kw):
        self.messages.append({"content": content, "embed": embed, "view": view})

    async def edit_message(self, content=None, embed=None, view=None, **kw):
        self.messages.append({"content": content, "embed": embed, "view": view})

    async def send_modal(self, modal):
        self.messages.append({"modal": modal})

    async def defer(self, ephemeral=False, **kw):
        self.deferred = True


class FakeFollowup:
    def __init__(self):
        self.messages = []

    async def send(self, content=None, embed=None, view=None, ephemeral=False, **kw):
        self.messages.append({"content": content, "embed": embed, "view": view})


class FakeGuild:
    def __init__(self):
        self.me = FakeAuthor("The Bot", 1)


class FakeInteraction:
    def __init__(self, bot, user=None):
        self.client = bot
        self.user = user or FakeAuthor()
        self.guild = FakeGuild()
        self.response = FakeResponse()
        self.followup = FakeFollowup()


def fill_modal(modal, values):
    """values: {label: text}. Writes _value, which is what .value reads."""
    inputs = [c for c in modal.children if isinstance(c, discord.ui.TextInput)]
    for child in inputs:
        child._value = values[child.label]
    return inputs


class TestFilamentLogging(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="filament-test-")
        os.environ["FILAMENT_DATA_PATH"] = self.tmp
        self.dm = FilamentDataManager(self.tmp)
        self.filament_id = self.dm.add_inventory_item("PLA", "Sunlu", "Black", 1000.0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("FILAMENT_DATA_PATH", None)

    async def _noop(self):
        return None

    async def test_log_usage_stores_names_and_print_description(self):
        self.dm.log_usage(
            "Connor Klute", self.filament_id, 42.5,
            first_name="Connor", last_name="Klute",
            print_description="Robot chassis brackets",
        )
        logs = self.dm.get_logs()
        self.assertEqual(len(logs), 1)
        entry = logs[0]
        self.assertEqual(entry["user"], "Connor Klute")
        self.assertEqual(entry["first_name"], "Connor")
        self.assertEqual(entry["last_name"], "Klute")
        self.assertEqual(entry["print_description"], "Robot chassis brackets")
        self.assertEqual(entry["amount_used"], 42.5)
        self.assertEqual(entry["filament_desc"], "Black PLA")

    async def test_log_usage_defaults_new_fields_when_omitted(self):
        # Old three-argument callers must still work and not crash.
        self.dm.log_usage("Legacy User", self.filament_id, 10.0)
        entry = self.dm.get_logs()[0]
        self.assertEqual(entry["first_name"], "")
        self.assertEqual(entry["last_name"], "")
        self.assertEqual(entry["print_description"], "")

    async def test_csv_export_includes_print_description(self):
        self.dm.log_usage(
            "Connor Klute", self.filament_id, 42.5,
            first_name="Connor", last_name="Klute",
            print_description="Robot chassis brackets",
        )
        csv_data = self.dm.export_logs_to_csv()
        self.assertIn("Print Description", csv_data)
        self.assertIn("Robot chassis brackets", csv_data)
        self.assertIn("Connor Klute", csv_data)

    async def test_modal_captures_all_four_fields(self):
        bot = FilamentBot(intents=discord.Intents.none())
        bot.update_dashboards = self._noop
        interaction = FakeInteraction(bot)

        modal = LogUsageModal(bot, self.filament_id, "Black PLA")
        inputs = fill_modal(modal, {
            "First Name": "Connor",
            "Last Name": "Klute",
            "What are you printing?": "Robot chassis brackets",
            "Amount Used (g)": "42.5",
        })
        self.assertEqual(len(inputs), 4)

        await modal.on_submit(interaction)

        logs = bot.data_manager.get_logs()
        self.assertEqual(len(logs), 1)
        entry = logs[0]
        self.assertEqual(entry["first_name"], "Connor")
        self.assertEqual(entry["last_name"], "Klute")
        self.assertEqual(entry["print_description"], "Robot chassis brackets")
        self.assertEqual(entry["amount_used"], 42.5)
        self.assertEqual(entry["user"], "Connor Klute")
        self.assertEqual(entry["filament_id"], self.filament_id)

        item = next(i for i in bot.data_manager.get_inventory() if i["id"] == self.filament_id)
        self.assertAlmostEqual(item["weight_g"], 957.5)

        # Modal answered exactly once (3 second response window).
        self.assertEqual(len(interaction.response.messages), 1)
        self.assertIn("Connor Klute", interaction.response.messages[0]["content"])
        self.assertIn("Robot chassis brackets", interaction.response.messages[0]["content"])

    async def test_modal_rejects_non_numeric_amount(self):
        bot = FilamentBot(intents=discord.Intents.none())
        bot.update_dashboards = self._noop
        interaction = FakeInteraction(bot)

        modal = LogUsageModal(bot, self.filament_id, "Black PLA")
        fill_modal(modal, {
            "First Name": "Connor",
            "Last Name": "Klute",
            "What are you printing?": "Bracket",
            "Amount Used (g)": "abc",
        })

        await modal.on_submit(interaction)

        self.assertEqual(bot.data_manager.get_logs(), [])
        self.assertEqual(len(interaction.response.messages), 1)
        self.assertIn("Invalid amount", interaction.response.messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
