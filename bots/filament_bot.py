import discord
from discord import ui
from discord.ext import tasks
import os
import hmac
import json
import asyncio
from typing import List, Dict, Optional
import bot_config
from utils.filament_data_manager import FilamentDataManager

# --- Configuration Management ---
CONFIG_FILE = "filament_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# --- Project pools ---
#
# A project pool is a tag on the shared inventory, not a second inventory. That
# makes "the project pool is part of the main pool" true by construction: the
# spool is an ordinary main-pool spool that happens to also be listed here. Same
# for usage: project logs go into the same log file with a project tag, so they
# land in the main Daily/Weekly/Monthly/Total with no extra aggregation.
#
# PROJECTS is the single source of truth for which pools exist. To add one:
#   1. add an entry here
#   2. add PROJECT_<KEY>_CHANNEL_ID and PROJECT_<KEY>_PIN to .env on the server
#   3. run !project setup <key> in that project's channel
# Nothing else in this file needs to change: the pickers, the pool listing and
# the env var names are all derived from this dict.
PROJECTS = {
    "wheelchair": "3D Printed Wheelchair",
}

# The project that has a live dashboard today. Kept as a name so the existing
# commands and helpers keep working unchanged.
PROJECT_KEY = "wheelchair"
PROJECT_DISPLAY_NAME = PROJECTS[PROJECT_KEY]
PROJECT_ACCENT = 0x8E44AD

# Sentinel for "not in any project pool" in the destination picker.
MAIN_POOL_VALUE = "__main__"


def project_display(project):
    return PROJECTS.get(project, project)


def project_channel_env(project):
    return "PROJECT_{}_CHANNEL_ID".format(project.upper())


def project_pin_env(project):
    return "PROJECT_{}_PIN".format(project.upper())


def env_int(name):
    """Read an integer env var, treating blank/missing/non-numeric as not set.

    os.getenv(name, default) returns "" for a key that is present but blank, and
    .env.example ships blank channel ids, so int() on the raw value is a live
    crash. None means "not configured".
    """
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"FilamentBot: {name} is not a numeric channel id ({raw!r}); ignoring it.")
        return None


def project_pin(project=PROJECT_KEY):
    """A project PIN, read from .env only. Never rendered into Discord."""
    return (os.getenv(project_pin_env(project)) or '').strip()


def project_pin_configured(project=PROJECT_KEY):
    return bool(project_pin(project))


def project_pin_matches(candidate, project=PROJECT_KEY):
    """Constant-time PIN check. A blank configured PIN never matches."""
    expected = project_pin(project)
    if not expected:
        return False
    return hmac.compare_digest(str(candidate or ''), expected)

# --- Modals ---
class LogUsageModal(ui.Modal, title="Log Filament Usage"):
    first_name = ui.TextInput(label="First Name", placeholder="Enter your first name", min_length=1, max_length=50)
    last_name = ui.TextInput(label="Last Name", placeholder="Enter your last name", min_length=1, max_length=50)
    print_desc = ui.TextInput(label="What are you printing?", placeholder="e.g., Robot chassis brackets", min_length=1, max_length=100)
    amount = ui.TextInput(label="Amount Used (g)", placeholder="e.g. 50.5", min_length=1, max_length=10)

    def __init__(self, bot, filament_id, filament_name, project=None):
        super().__init__()
        self.bot = bot
        self.filament_id = filament_id
        self.filament_name = filament_name
        self.project = project

    async def on_submit(self, interaction: discord.Interaction):
        # Project logging is PIN-gated, so every reply on that path stays private.
        ephemeral = bool(self.project)
        delete_after = None if ephemeral else 5
        try:
            amount_val = float(self.amount.value)
            
            # Combine first and last name for the log entry
            user_display = f"{self.first_name.value} {self.last_name.value}".strip()
            
            self.bot.data_manager.log_usage(
                user_display,
                self.filament_id,
                amount_val,
                first_name=self.first_name.value,
                last_name=self.last_name.value,
                print_description=self.print_desc.value,
                project=self.project
            )
            self.bot.data_manager.update_filament_weight(self.filament_id, amount_val)
            
            note = (f"Logged **{amount_val}g** of **{self.filament_name}** by **{user_display}** "
                    f"for: {self.print_desc.value}.")
            if self.project:
                note += f"\nCharged to the {PROJECT_DISPLAY_NAME} pool. It counts in the main filament stats too."
            await interaction.response.send_message(note, ephemeral=ephemeral, delete_after=delete_after)
            # Trigger dashboard updates
            await self.bot.update_dashboards()
            
        except ValueError:
            await interaction.response.send_message("Invalid amount. Please enter a number.", ephemeral=ephemeral, delete_after=delete_after)
        except Exception as e:
            print(f"Error logging usage: {e}")
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=ephemeral, delete_after=delete_after)

class AddFilamentModal(ui.Modal, title="Add New Filament"):
    brand = ui.TextInput(label="Brand", placeholder="e.g., Elegoo", max_length=50)
    type_name = ui.TextInput(label="Type", placeholder="e.g., PLA", max_length=20)
    color = ui.TextInput(label="Color", placeholder="e.g., Matte Black", max_length=30)
    weight = ui.TextInput(label="Initial Weight (g)", placeholder="e.g., 1000", max_length=10)

    def __init__(self, bot, admin_only=False, projects=None):
        chosen = list(projects or [])
        if chosen:
            # Modal titles cap at 45 characters, so trim rather than raise.
            title = ("Add to " + ", ".join(project_display(p) for p in chosen))[:45]
        elif admin_only:
            title = "Add Admin Filament"
        else:
            title = "Add New Filament"
        super().__init__(title=title)
        self.bot = bot
        self.admin_only = admin_only
        self.projects = chosen

    def pool_label(self):
        """Human name for the destination, used in the confirmation."""
        if self.projects:
            return ", ".join(project_display(p) for p in self.projects) + " pool"
        if self.admin_only:
            return "admin pool"
        return "main pool"

    async def on_submit(self, interaction: discord.Interaction):
        try:
            weight_val = float(self.weight.value)
            new_id = self.bot.data_manager.add_inventory_item(
                self.type_name.value, 
                self.brand.value, 
                self.color.value, 
                weight_val,
                self.admin_only,
                projects=self.projects
            )
            await interaction.response.send_message(
                f"Added **{self.brand.value} {self.type_name.value} ({self.color.value})** "
                f"with ID **{new_id}** to the {self.pool_label()}.",
                delete_after=5
            )
            await self.bot.update_dashboards()

        except ValueError:
             await interaction.response.send_message("❌ Invalid weight. Please enter a number.", ephemeral=True)
        except Exception as e:
            print(f"Error adding filament: {e}")
            await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

class EditFilamentModal(ui.Modal, title="Edit Filament Details"):
    brand = ui.TextInput(label="Brand", max_length=50)
    type_name = ui.TextInput(label="Type", max_length=20)
    color = ui.TextInput(label="Color", max_length=30)
    weight = ui.TextInput(label="Current Weight (g)", max_length=10)

    def __init__(self, bot, filament_id, current_data):
        super().__init__()
        self.bot = bot
        self.filament_id = filament_id
        
        # Pre-fill values
        self.brand.default = current_data.get('brand', '')
        self.type_name.default = current_data.get('type', '')
        self.color.default = current_data.get('color', '')
        self.weight.default = str(current_data.get('weight_g', 0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Update data
            base_weight = float(self.weight.value)
            
            success = self.bot.data_manager.update_inventory_item(
                self.filament_id,
                brand=self.brand.value,
                type=self.type_name.value,
                color=self.color.value,
                weight_g=base_weight
            )
            
            if success:
                await interaction.response.send_message(
                    f"✅ Updated filament ID **{self.filament_id}**:\n"
                    f"{self.brand.value} {self.type_name.value} - {self.color.value} ({base_weight}g)",
                    ephemeral=True
                )
                await self.bot.update_dashboards()
            else:
                await interaction.response.send_message("❌ Failed to update filament. ID not found.", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Invalid weight format.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class EditLogModal(ui.Modal, title="Edit Log"):
    user_name = ui.TextInput(label="User Name", max_length=100)
    amount = ui.TextInput(label="Amount Used (g)", max_length=10)

    def __init__(self, bot, log_id, current_data):
        super().__init__()
        self.bot = bot
        self.log_id = log_id
        
        # Pre-fill values
        self.user_name.default = current_data.get('user', '')
        self.amount.default = str(current_data.get('amount_used', 0))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_amount = float(self.amount.value)
            success = self.bot.data_manager.update_log(
                self.log_id,
                new_user=self.user_name.value,
                new_amount=new_amount
            )
            
            if success:
                await interaction.response.send_message(f"✅ Updated log **{self.log_id}**.", ephemeral=True)
                await self.bot.update_dashboards()
            else:
                await interaction.response.send_message("❌ Failed to update log.", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Invalid amount format.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# --- Select Menus ---
class FilamentSelect(ui.Select):
    def __init__(self, bot):
        self.bot: 'FilamentBot' = bot
        options = []
        inventory = self.bot.data_manager.get_inventory()
        filtered_inv = [i for i in inventory if not i.get('admin_only', False)]
        sorted_inv = sorted(filtered_inv, key=lambda x: (x.get('type', ''), x.get('color', '')))
        
        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            desc = f"Remaining: {item['weight_g']}g"
            if len(label) > 100: label = label[:97] + "..."
            
            options.append(discord.SelectOption(
                label=label, 
                description=desc, 
                value=str(item['id'])
            ))
            if len(options) >= 25: break 

        if not options:
            options.append(discord.SelectOption(label="No filaments available", value="-1"))

        super().__init__(placeholder="Select a filament...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        name = f"{item['color']} {item['type']}" if item else "Unknown"
        
        await interaction.response.send_modal(LogUsageModal(self.bot, filament_id, name))

class AdminFilamentSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        inventory = self.bot.data_manager.get_inventory()
        sorted_inv = sorted(inventory, key=lambda x: (x.get('type', ''), x.get('color', '')))
        
        for item in sorted_inv:
            tag = "🔒 " if item.get('admin_only', False) else ""
            label = f"{tag}{item['brand']} {item['type']} - {item['color']}"
            desc = f"Remaining: {item['weight_g']}g"
            if len(label) > 100: label = label[:97] + "..."
            
            options.append(discord.SelectOption(
                label=label, 
                description=desc, 
                value=str(item['id'])
            ))
            if len(options) >= 25: break 

        if not options:
            options.append(discord.SelectOption(label="No filaments available", value="-1"))

        super().__init__(placeholder="Select a filament (Admin)...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        name = f"{item['color']} {item['type']}" if item else "Unknown"
        
        await interaction.response.send_modal(LogUsageModal(self.bot, filament_id, name))

class EditFilamentSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        inventory = self.bot.data_manager.get_inventory()
        # Sort for easier finding
        sorted_inv = sorted(inventory, key=lambda x: (x.get('brand', ''), x.get('type', ''), x.get('color', '')))
        
        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            if len(label) > 100: label = label[:97] + "..."
            
            options.append(discord.SelectOption(
                label=label,
                description=f"ID: {item['id']} | {item['weight_g']}g",
                value=str(item['id'])
            ))
            if len(options) >= 25: break

        if not options:
            options.append(discord.SelectOption(label="No filaments to edit", value="-1"))

        super().__init__(placeholder="Select filament to edit...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        
        if item:
            await interaction.response.send_modal(EditFilamentModal(self.bot, filament_id, item))
        else:
            await interaction.response.send_message("❌ Filament not found!", ephemeral=True)

class DeleteFilamentSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        inventory = self.bot.data_manager.get_inventory()
        sorted_inv = sorted(inventory, key=lambda x: (x.get('brand', ''), x.get('type', ''), x.get('color', '')))
        
        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            if len(label) > 100: label = label[:97] + "..."
            
            options.append(discord.SelectOption(
                label=label,
                description=f"ID: {item['id']} | {item['weight_g']}g",
                value=str(item['id']),
                emoji="🗑️"
            ))
            if len(options) >= 25: break

        if not options:
            options.append(discord.SelectOption(label="No filaments to delete", value="-1"))

        super().__init__(placeholder="Select filament to DELETE...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        
        if item:
            # Confirm deletion logic could go here, but for now direct delete
            success = self.bot.data_manager.delete_inventory_item(filament_id)
            if success:
                await interaction.response.send_message(
                    f"🗑️ **Deleted Filament**: {item['brand']} {item['type']} - {item['color']}", 
                    ephemeral=True
                )
                await self.bot.update_dashboards()
            else:
                await interaction.response.send_message("❌ Failed to delete item.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Filament not found!", ephemeral=True)

class MoveToRegularSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        inventory = self.bot.data_manager.get_inventory()
        admin_inv = [i for i in inventory if i.get('admin_only', False)]
        sorted_inv = sorted(admin_inv, key=lambda x: (x.get('brand', ''), x.get('type', ''), x.get('color', '')))
        
        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            if len(label) > 100: label = label[:97] + "..."
            
            options.append(discord.SelectOption(
                label=label,
                description=f"ID: {item['id']} | {item['weight_g']}g",
                value=str(item['id']),
                emoji="➡️"
            ))
            if len(options) >= 25: break

        if not options:
            options.append(discord.SelectOption(label="No admin filaments", value="-1"))

        super().__init__(placeholder="Select admin filament to move...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        if filament_id == -1:
            await interaction.response.send_message("❌ No filaments available to move.", ephemeral=True)
            return
            
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        
        if item:
            success = self.bot.data_manager.update_inventory_item(filament_id, admin_only=False)
            if success:
                await interaction.response.send_message(
                    f"✅ Moved **{item['brand']} {item['type']} - {item['color']}** to the regular pool.", 
                    ephemeral=True
                )
                await self.bot.update_dashboards()
            else:
                await interaction.response.send_message("❌ Failed to move filament.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Filament not found!", ephemeral=True)

class EditLogSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        logs = self.bot.data_manager.get_logs()
        recent_logs = sorted(logs, key=lambda x: x.get('id', 0), reverse=True)[:25]
        
        for item in recent_logs:
            lbl = f"{item['user']} - {item.get('filament_desc', 'Unknown')}"
            if len(lbl) > 100: lbl = lbl[:97] + "..."
            
            options.append(discord.SelectOption(
                label=lbl,
                description=f"ID: {item.get('id', '?')} | {item.get('amount_used', 0)}g | {item.get('timestamp', '')[:10]}",
                value=str(item.get('id', 0))
            ))

        if not options:
            options.append(discord.SelectOption(label="No logs available", value="-1"))

        super().__init__(placeholder="Select recent log to edit...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        log_id = int(self.values[0])
        if log_id == -1:
            await interaction.response.send_message("❌ No logs available to select.", ephemeral=True)
            return
        logs = self.bot.data_manager.get_logs()
        item = next((x for x in logs if x.get('id') == log_id), None)
        
        if item:
            await interaction.response.send_modal(EditLogModal(self.bot, log_id, item))
        else:
            await interaction.response.send_message("❌ Log not found!", ephemeral=True)

class DeleteLogSelect(ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        logs = self.bot.data_manager.get_logs()
        recent_logs = sorted(logs, key=lambda x: x.get('id', 0), reverse=True)[:25]
        
        for item in recent_logs:
            lbl = f"{item['user']} - {item.get('filament_desc', 'Unknown')}"
            if len(lbl) > 100: lbl = lbl[:97] + "..."
            
            options.append(discord.SelectOption(
                label=lbl,
                description=f"ID: {item.get('id', '?')} | {item.get('amount_used', 0)}g | {item.get('timestamp', '')[:10]}",
                value=str(item.get('id', 0)),
                emoji="🗑️"
            ))

        if not options:
            options.append(discord.SelectOption(label="No logs available", value="-1"))

        super().__init__(placeholder="Select recent log to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        log_id = int(self.values[0])
        if log_id == -1:
            await interaction.response.send_message("❌ No logs available to select.", ephemeral=True)
            return
        success = self.bot.data_manager.delete_log(log_id)
        if success:
            await interaction.response.send_message(f"🗑️ **Deleted Log** (ID: {log_id}). Restored inventory.", ephemeral=True)
            await self.bot.update_dashboards()
        else:
            await interaction.response.send_message("❌ Failed to delete log.", ephemeral=True)

# --- Project Views (3D Printed Wheelchair) ---
#
# The project channel gets its own dashboard. Logging against the project is
# gated behind the project PIN; the PIN is never posted, never embedded, and the
# whole flow answers ephemerally so nothing about it is visible to anyone else
# in the server.

def is_admin(interaction):
    perms = getattr(interaction.user, 'guild_permissions', None)
    return bool(perms and perms.administrator)


def scope_custom_ids(view, project):
    """Rewrite a persistent view's custom_ids to be per-project.

    `custom_id` is fixed by the `@ui.button` decorator at class-definition time,
    so it is rewritten here instead. That is what lets one class serve several
    project pools while every button still gets a stable, unique custom_id (which
    is what persistent views require).
    """
    prefix = "filament_project_"
    for child in view.children:
        base = getattr(child, "custom_id", None)
        if base and base.startswith(prefix):
            child.custom_id = prefix + project + "_" + base[len(prefix):]


class PoolDestinationSelect(ui.Select):
    """Pick which pool a newly added spool belongs to.

    Driven entirely by the PROJECTS registry, so a new project appears here with
    no change to this class. "Main pool only" is the no-project choice.
    """

    def __init__(self, bot):
        self.bot = bot
        options = [discord.SelectOption(
            label="Main pool only",
            description="Not part of any project",
            value=MAIN_POOL_VALUE,
        )]
        for key, display in PROJECTS.items():
            count = len(self.bot.data_manager.get_project_inventory(key))
            options.append(discord.SelectOption(
                label=f"Project: {display}",
                description=f"{count} spool(s) currently allocated",
                value=key,
            ))
        super().__init__(placeholder="Where should this spool go?",
                         min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        choice = self.values[0]
        projects = [] if choice == MAIN_POOL_VALUE else [choice]
        await interaction.response.send_modal(
            AddFilamentModal(self.bot, admin_only=False, projects=projects))


class ProjectPickerSelect(ui.Select):
    """Pick a project, then open its pool controls.

    The project channel carries only the logging button, so pool management is
    reached from the admin panel instead of from a second message in the project
    channel.
    """

    def __init__(self, bot):
        self.bot = bot
        options = [
            discord.SelectOption(
                label=display,
                description=f"{len(bot.data_manager.get_project_inventory(key))} spool(s) allocated",
                value=key,
            )
            for key, display in PROJECTS.items()
        ]
        super().__init__(placeholder="Select a project...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        project = self.values[0]
        await interaction.response.send_message(
            embed=self.bot.get_project_admin_embed(project),
            view=ProjectAdminView(self.bot, project),
            ephemeral=True)


class ProjectFilamentSelect(ui.Select):
    """Only filament tagged into one project pool."""

    def __init__(self, bot, project=PROJECT_KEY):
        self.bot = bot
        self.project = project
        options = []
        inventory = self.bot.data_manager.get_project_inventory(project)
        filtered = [i for i in inventory if not i.get('admin_only', False)]
        sorted_inv = sorted(filtered, key=lambda x: (x.get('type', ''), x.get('color', '')))

        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            desc = f"Remaining: {item['weight_g']}g"
            if len(label) > 100: label = label[:97] + "..."

            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(item['id'])
            ))
            if len(options) >= 25: break

        if not options:
            options.append(discord.SelectOption(label="No project filament available", value="-1"))

        super().__init__(placeholder="Select project filament...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        if filament_id == -1:
            await interaction.response.send_message(
                "No filament is allocated to the project pool yet.", ephemeral=True)
            return
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        name = f"{item['color']} {item['type']}" if item else "Unknown"

        await interaction.response.send_modal(
            LogUsageModal(self.bot, filament_id, name, project=self.project))


class ProjectPinModal(ui.Modal):
    """PIN gate for one project's usage.

    The PIN itself is never echoed back and this modal's contents are only ever
    seen by the person who opened it, which is what keeps it out of the server.
    """

    pin = ui.TextInput(label="Project PIN", placeholder="Enter the project PIN", min_length=1, max_length=64)

    def __init__(self, bot, project=PROJECT_KEY):
        super().__init__(title=("{} Access".format(project_display(project)))[:45])
        self.bot = bot
        self.project = project

    async def on_submit(self, interaction: discord.Interaction):
        if not project_pin_configured(self.project):
            await interaction.response.send_message(
                f"Project logging is not configured on the server ({project_pin_env(self.project)} is unset). "
                "Ask an officer.",
                ephemeral=True
            )
            return

        if not project_pin_matches(self.pin.value, self.project):
            # Deliberately vague: no hint about length or characters.
            print(f"ProjectPin: rejected a PIN attempt for the {project_display(self.project)} project.")
            await interaction.response.send_message("Incorrect PIN.", ephemeral=True)
            return

        view = ui.View()
        select = ProjectFilamentSelect(self.bot, self.project)
        if not select.options or select.options[0].value == "-1":
            await interaction.response.send_message(
                "Access granted, but no filament is allocated to the project pool yet.", ephemeral=True)
            return
        view.add_item(select)
        await interaction.response.send_message(
            "Access granted. Select the filament you used:", view=view, ephemeral=True)


class AttachToProjectSelect(ui.Select):
    """Tag an existing main-pool spool into one project pool."""

    def __init__(self, bot, project=PROJECT_KEY):
        self.bot = bot
        self.project = project
        options = []
        inventory = self.bot.data_manager.get_inventory()
        available = [i for i in inventory if project not in i.get('projects', [])]
        sorted_inv = sorted(available, key=lambda x: (x.get('brand', ''), x.get('type', ''), x.get('color', '')))

        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            if len(label) > 100: label = label[:97] + "..."
            options.append(discord.SelectOption(
                label=label,
                description=f"ID: {item['id']} | {item['weight_g']}g",
                value=str(item['id'])
            ))
            if len(options) >= 25: break

        if not options:
            options.append(discord.SelectOption(label="Every filament is already in the pool", value="-1"))

        super().__init__(placeholder="Add existing filament to the project pool...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        item_id = int(self.values[0])
        if item_id == -1:
            await interaction.response.send_message("Nothing left to add to the pool.", ephemeral=True)
            return
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == item_id), None)
        success = self.bot.data_manager.set_project_membership(item_id, self.project, True)
        if success and item:
            await interaction.response.send_message(
                f"Added **{item['brand']} {item['type']} - {item['color']}** to the {project_display(self.project)} pool. "
                f"It stays in the main pool.",
                ephemeral=True
            )
            await self.bot.update_dashboards()
        else:
            await interaction.response.send_message("Failed to update the project pool.", ephemeral=True)


class DetachFromProjectSelect(ui.Select):
    """Remove a spool from one project pool. It remains in the main pool."""

    def __init__(self, bot, project=PROJECT_KEY):
        self.bot = bot
        self.project = project
        options = []
        inventory = self.bot.data_manager.get_project_inventory(project)
        sorted_inv = sorted(inventory, key=lambda x: (x.get('brand', ''), x.get('type', ''), x.get('color', '')))

        for item in sorted_inv:
            label = f"{item['brand']} {item['type']} - {item['color']}"
            if len(label) > 100: label = label[:97] + "..."
            options.append(discord.SelectOption(
                label=label,
                description=f"ID: {item['id']} | {item['weight_g']}g",
                value=str(item['id']),
                emoji="\U0001F5D1\uFE0F"
            ))
            if len(options) >= 25: break

        if not options:
            options.append(discord.SelectOption(label="The pool is already empty", value="-1"))

        super().__init__(placeholder="Remove filament from the project pool...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        item_id = int(self.values[0])
        if item_id == -1:
            await interaction.response.send_message("The project pool is already empty.", ephemeral=True)
            return
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == item_id), None)
        success = self.bot.data_manager.set_project_membership(item_id, self.project, False)
        if success and item:
            await interaction.response.send_message(
                f"Removed **{item['brand']} {item['type']} - {item['color']}** from the {project_display(self.project)} pool. "
                f"It is still in the main pool.",
                ephemeral=True
            )
            await self.bot.update_dashboards()
        else:
            await interaction.response.send_message("Failed to update the project pool.", ephemeral=True)


class ProjectDashboardView(ui.View):
    def __init__(self, bot, project=PROJECT_KEY):
        super().__init__(timeout=None)
        self.bot = bot
        self.project = project
        scope_custom_ids(self, project)

    @ui.button(label="Log Project Usage", style=discord.ButtonStyle.success, custom_id="filament_project_log")
    async def log_project_usage_btn(self, interaction: discord.Interaction, button: ui.Button):
        # PIN modal first; the filament picker only appears once the PIN checks out.
        await interaction.response.send_modal(ProjectPinModal(self.bot, self.project))


class ProjectAdminView(ui.View):
    def __init__(self, bot, project=PROJECT_KEY):
        super().__init__(timeout=None)
        self.bot = bot
        self.project = project
        scope_custom_ids(self, project)

    @ui.button(label="Add Filament to Pool", style=discord.ButtonStyle.primary, custom_id="filament_project_add")
    async def add_pool_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        await interaction.response.send_modal(
            AddFilamentModal(self.bot, admin_only=False, projects=[self.project]))

    @ui.button(label="Add Existing to Pool", style=discord.ButtonStyle.primary, custom_id="filament_project_attach")
    async def attach_pool_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        view = ui.View()
        select = AttachToProjectSelect(self.bot, self.project)
        if not select.options or select.options[0].value == "-1":
            await interaction.response.send_message("Every filament is already in the project pool.", ephemeral=True)
            return
        view.add_item(select)
        await interaction.response.send_message(
            "Select a filament to add to the project pool:", view=view, ephemeral=True)

    @ui.button(label="Remove from Pool", style=discord.ButtonStyle.danger, custom_id="filament_project_detach")
    async def detach_pool_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        view = ui.View()
        select = DetachFromProjectSelect(self.bot, self.project)
        if not select.options or select.options[0].value == "-1":
            await interaction.response.send_message("The project pool is already empty.", ephemeral=True)
            return
        view.add_item(select)
        await interaction.response.send_message(
            "Select a filament to remove from the project pool:", view=view, ephemeral=True)

    @ui.button(label="Export Project Logs", style=discord.ButtonStyle.secondary, custom_id="filament_project_export")
    async def export_project_logs_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        csv_data = self.bot.data_manager.export_logs_to_csv(project=self.project)
        import io
        file = discord.File(io.StringIO(csv_data), filename=f"{self.project}_filament_logs.csv")
        await interaction.response.send_message(
            f"Here is the {project_display(self.project)} usage log:", file=file, ephemeral=True)


# --- Public Dashboard View ---
class PublicDashboardView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Log Usage", style=discord.ButtonStyle.success, custom_id="filament_public_log")
    async def log_usage_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = FilamentSelect(self.bot)
        if not select.options:
             await interaction.response.send_message("No filament in inventory!", delete_after=5)
             return
        view.add_item(select)
        await interaction.response.send_message("Select the filament you used:", view=view, ephemeral=True)

# --- Admin Dashboard View ---
class AdminDashboardView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Log Admin Usage", style=discord.ButtonStyle.success, custom_id="filament_admin_log")
    async def log_admin_usage_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = AdminFilamentSelect(self.bot)
        if not select.options:
             await interaction.response.send_message("No filament available!", ephemeral=True)
             return
        view.add_item(select)
        await interaction.response.send_message("Select filament you used (Admin):", view=view, ephemeral=True)

    @ui.button(label="Add Filament", style=discord.ButtonStyle.primary, custom_id="filament_admin_add")
    async def add_filament_btn(self, interaction: discord.Interaction, button: ui.Button):
        # Ask which pool first so project spools can be created from the main
        # panel, not only from the project channel.
        view = ui.View()
        view.add_item(PoolDestinationSelect(self.bot))
        await interaction.response.send_message(
            "Where should the new spool go?", view=view, ephemeral=True)

    @ui.button(label="Add Admin Filament", style=discord.ButtonStyle.primary, custom_id="filament_admin_add_admin")
    async def add_admin_filament_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddFilamentModal(self.bot, admin_only=True))

    @ui.button(label="Edit Filament", style=discord.ButtonStyle.primary, custom_id="filament_admin_edit")
    async def edit_filament_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = EditFilamentSelect(self.bot)
        if not select.options:
             await interaction.response.send_message("No filament to edit!", ephemeral=True)
             return
        view.add_item(select)
        await interaction.response.send_message("Select filament to edit:", view=view, ephemeral=True)

    @ui.button(label="Delete Filament", style=discord.ButtonStyle.danger, custom_id="filament_admin_delete")
    async def delete_filament_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = DeleteFilamentSelect(self.bot)
        if not select.options:
             await interaction.response.send_message("No filament to delete!", ephemeral=True)
             return
        view.add_item(select)
        await interaction.response.send_message("⚠️ **SELECT FILAMENT TO DELETE** ⚠️", view=view, ephemeral=True)

    @ui.button(label="Project Pools", style=discord.ButtonStyle.primary, custom_id="filament_admin_project_pools", row=2)
    async def project_pools_btn(self, interaction: discord.Interaction, button: ui.Button):
        # Pool management lives here rather than in the project channel, which
        # carries only the logging button.
        if not is_admin(interaction):
            await interaction.response.send_message("Administrator permissions required.", ephemeral=True)
            return
        if not PROJECTS:
            await interaction.response.send_message("No projects are registered.", ephemeral=True)
            return
        view = ui.View()
        view.add_item(ProjectPickerSelect(self.bot))
        await interaction.response.send_message(
            "Select a project pool to manage:", view=view, ephemeral=True)

    @ui.button(label="Export Logs", style=discord.ButtonStyle.secondary, custom_id="filament_admin_export")
    async def export_logs_btn(self, interaction: discord.Interaction, button: ui.Button):
        csv_data = self.bot.data_manager.export_logs_to_csv()
        
        # Create a temporary file to send
        import io
        file = discord.File(io.StringIO(csv_data), filename="filament_logs_export.csv")
        
        await interaction.response.send_message("📊 Here is the latest usage log:", file=file, ephemeral=True)

    @ui.button(label="Edit Log", style=discord.ButtonStyle.secondary, custom_id="filament_admin_edit_log", row=1)
    async def edit_log_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = EditLogSelect(self.bot)
        if not select.options:
             await interaction.response.send_message("No logs available!", ephemeral=True)
             return
        view.add_item(select)
        await interaction.response.send_message("Select a recent log to edit:", view=view, ephemeral=True)

    @ui.button(label="Delete Log", style=discord.ButtonStyle.danger, custom_id="filament_admin_delete_log", row=1)
    async def delete_log_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = DeleteLogSelect(self.bot)
        if not select.options:
             await interaction.response.send_message("No logs available!", ephemeral=True)
             return
        view.add_item(select)
        await interaction.response.send_message("Select a recent log to delete:", view=view, ephemeral=True)

    @ui.button(label="Move to Regular", style=discord.ButtonStyle.primary, custom_id="filament_admin_move_regular", row=1)
    async def move_to_regular_btn(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View()
        select = MoveToRegularSelect(self.bot)
        if not select.options or select.options[0].value == "-1":
             await interaction.response.send_message("No admin filaments available!", ephemeral=True)
             return
        view.add_item(select)
        await interaction.response.send_message("Select admin filament to move to regular pool:", view=view, ephemeral=True)

# --- Main Bot Class ---
class FilamentBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data_path = os.getenv('FILAMENT_DATA_PATH')
        if not data_path:
            print("ERROR: FILAMENT_DATA_PATH not set in .env")
            data_path = "./data" # Fallback
            
        self.data_manager = FilamentDataManager(data_path)
        self.config = load_config()

    async def setup_hook(self):
        # Register persistent views so buttons work after restart
        self.add_view(PublicDashboardView(self))
        self.add_view(AdminDashboardView(self))
        # One dashboard per registered project. The project channel carries only
        # the logging button; pool management is reached from the admin panel
        # instead, so ProjectAdminView is built on demand and needs no persistent
        # registration here.
        for key in PROJECTS:
            self.add_view(ProjectDashboardView(self, key))
        self.auto_refresh.start()

    @tasks.loop(minutes=1)
    async def auto_refresh(self):
        await self.update_dashboards()
    
    @auto_refresh.before_loop
    async def before_auto_refresh(self):
        await self.wait_until_ready()

    async def on_ready(self):
        print(f'Filament Tracker logged in as {self.user} (ID: {self.user.id})')
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.FILAMENT_BOT_NICKNAME)
            except:
                pass

    # --- Per-project config ---
    #
    # Stored as config['projects'][key] = {channel_id, message_id, admin_message_id}.
    # The flat project_channel_id / project_message_id / project_admin_message_id
    # keys written by the first version of this feature are still read as a
    # fallback, so an existing filament_config.json keeps working.

    def project_ids(self, project):
        entry = (self.config.get('projects') or {}).get(project) or {}
        if project == PROJECT_KEY:
            return {
                'channel_id': entry.get('channel_id') or self.config.get('project_channel_id'),
                'message_id': entry.get('message_id') or self.config.get('project_message_id'),
                'admin_message_id': entry.get('admin_message_id') or self.config.get('project_admin_message_id'),
            }
        return dict(entry)

    def set_project_ids(self, project, **ids):
        entry = self.config.setdefault('projects', {}).setdefault(project, {})
        for key, value in ids.items():
            if value is not None:
                entry[key] = value

    def get_public_embed(self):
        stats = self.data_manager.get_consumption_stats()
        inventory = self.data_manager.get_inventory()
        
        embed = discord.Embed(
            title="Filament Inventory & Status",
            description="Live tracking of ELC 3D Printer Filament.",
            color=0x3498DB
        )
        
        # Stats Field
        stats_text = (
            f"Daily Used: {stats['daily']}g\n"
            f"Weekly Used: {stats['weekly']}g\n"
            f"Monthly Used: {stats['monthly']}g\n"
            f"Total Used: {stats['total']}g"
        )
        embed.add_field(name="Consumption Stats", value=stats_text, inline=False)
        
        if not inventory:
            embed.add_field(name="Inventory", value="No filament recorded.", inline=False)
        else:
            # Group by Type
            grouped = {}
            for item in inventory:
                ftype = item.get('type', 'Other')
                if ftype not in grouped: grouped[ftype] = []
                grouped[ftype].append(item)
            
            for ftype, items in grouped.items():
                content = ""
                for item in items:
                    admin_tag = " 🔒" if item.get('admin_only', False) else ""
                    content += f"{item['brand']} {item['color']}: {item['weight_g']}g{admin_tag}\n"
                embed.add_field(name=f"{ftype}", value=content, inline=False)
        
        embed.set_footer(text="Use the button below to log usage.")
        embed.timestamp = discord.utils.utcnow()
        return embed

    def get_admin_embed(self):
        embed = discord.Embed(
            title="Filament Admin Controls",
            description="Administrative tools for managing filament inventory.",
            color=0xE74C3C
        )
        embed.add_field(name="Instructions", value="• **Add Filament**: Register a new spool.\n• **Export Logs**: Download usage history as CSV.")
        return embed

    def get_project_embed(self, project=PROJECT_KEY):
        """Dashboard for one project channel.

        Shows the project pool (spools tagged into the project) alongside two sets
        of numbers: this project's usage, and the all-filament usage it feeds into.
        """
        project_items = self.data_manager.get_project_inventory(project)
        project_stats = self.data_manager.get_project_stats(project)
        overall_stats = self.data_manager.get_consumption_stats()

        embed = discord.Embed(
            title=f"{project_display(project)} - Filament",
            description=("Filament allocated to this project. Usage logged here is also counted in the "
                         "main filament stats."),
            color=PROJECT_ACCENT
        )

        if not project_items:
            embed.add_field(name="Project Pool", value="No filament allocated to this project yet.", inline=False)
        else:
            lines = []
            for item in project_items:
                lines.append(f"{item['brand']} {item['color']}: {item['weight_g']}g")
            embed.add_field(name="Project Pool", value="\n".join(lines), inline=False)

        embed.add_field(
            name="This Project",
            value=(f"Daily Used: {project_stats['daily']}g\n"
                   f"Weekly Used: {project_stats['weekly']}g\n"
                   f"Monthly Used: {project_stats['monthly']}g\n"
                   f"Total Used: {project_stats['total']}g"),
            inline=True
        )
        embed.add_field(
            name="All Filament",
            value=(f"Daily Used: {overall_stats['daily']}g\n"
                   f"Weekly Used: {overall_stats['weekly']}g\n"
                   f"Monthly Used: {overall_stats['monthly']}g\n"
                   f"Total Used: {overall_stats['total']}g"),
            inline=True
        )

        embed.set_footer(text="Logging project usage requires the project PIN.")
        embed.timestamp = discord.utils.utcnow()
        return embed

    def get_project_admin_embed(self, project=PROJECT_KEY):
        embed = discord.Embed(
            title=f"{project_display(project)} - Project Controls",
            description="Manage which filament is allocated to this project. Project filament is always part of the main pool.",
            color=PROJECT_ACCENT
        )
        embed.add_field(
            name="Instructions",
            value=("• **Add Filament to Pool**: register a new spool and allocate it here.\n"
                   "• **Add Existing to Pool**: allocate a spool that is already in the main inventory.\n"
                   "• **Remove from Pool**: unallocate a spool. It stays in the main inventory.\n"
                   "• **Export Project Logs**: this project's usage only.")
        )
        return embed

    async def update_dashboards(self):
        # Update Public Dashboard
        pub_chan_id = self.config.get('public_channel_id')
        pub_msg_id = self.config.get('public_message_id')
        
        if pub_chan_id and pub_msg_id:
            try:
                channel = self.get_channel(pub_chan_id) or await self.fetch_channel(pub_chan_id)
                message = await channel.fetch_message(pub_msg_id)
                await message.edit(embed=self.get_public_embed(), view=PublicDashboardView(self))
            except Exception as e:
                print(f"Failed to update Public Dashboard: {e}")

        # Admin dashboard doesn't need constant updating as it's static menu, but good to know

        # Update every registered project dashboard
        for key in PROJECTS:
            ids = self.project_ids(key)
            if not (ids.get('channel_id') and ids.get('message_id')):
                continue
            try:
                channel = self.get_channel(ids['channel_id']) or await self.fetch_channel(ids['channel_id'])
                message = await channel.fetch_message(ids['message_id'])
                await message.edit(embed=self.get_project_embed(key), view=ProjectDashboardView(self, key))
            except Exception as e:
                print(f"Failed to update the {key} project dashboard: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Command spelling: underscores are folded to spaces for command matching.
        # The repo's own !admin_setup uses an underscore while the other commands
        # use a space, so !wheelchair_setup is the natural thing to type. An
        # unmatched command is completely invisible rather than an error, because
        # the dashboard channels auto-delete user messages, so a typo looks like
        # the bot being broken. Accepting both spellings costs nothing.
        cmd = message.content.replace('_', ' ').strip()

        # Universal Admin Setup
        if cmd.startswith('!admin setup'):
            if not message.author.guild_permissions.administrator:
                 return 

            # Check configured admin channel
            admin_channel_id = os.getenv('ADMIN_CHANNEL_ID')
            if admin_channel_id and str(message.channel.id) != str(admin_channel_id):
                return
            
            # Post Admin Dashboard
            try:
                # Master Purge: Filament Bot clears the channel first
                # We limit to 100 messages to be safe, or just purge all if possible
                await message.channel.purge(limit=20)
                
                # We use the existing get_admin_embed and AdminDashboardView
                await message.channel.send(embed=self.get_admin_embed(), view=AdminDashboardView(self))
            except Exception as e:
                print(f"FilamentBot failed to post admin setup: {e}")
            return

        # Project setup: !project setup <key>, with !wheelchair setup as an alias
        project_key = None
        if cmd.startswith('!project setup'):
            parts = cmd.split()
            if len(parts) < 3 or not parts[2].strip():
                await message.channel.send(
                    "Usage: `!project setup <key>`. Known projects: " + ", ".join(PROJECTS))
                return
            project_key = parts[2].strip().lower()
            if project_key not in PROJECTS:
                await message.channel.send(
                    f"❌ Unknown project `{project_key}`. Known projects: " + ", ".join(PROJECTS))
                return
        elif cmd.startswith('!wheelchair setup'):
            project_key = PROJECT_KEY

        if project_key:
            if not message.author.guild_permissions.administrator:
                await message.channel.send("❌ Admin permissions required.")
                return

            display = project_display(project_key)
            channel_env = project_channel_env(project_key)
            project_channel_id = env_int(channel_env)
            if not project_channel_id:
                await message.channel.send(f"❌ Missing `{channel_env}` in `.env`.")
                return
            if not project_pin_configured(project_key):
                # Loud, because otherwise every project log attempt just gets refused.
                await message.channel.send(
                    f"⚠️ `{project_pin_env(project_key)}` is not set in `.env`, so {display} usage "
                    f"logging will refuse every attempt until it is."
                )

            try:
                project_channel = await self.fetch_channel(project_channel_id)
            except Exception as e:
                await message.channel.send(f"❌ Could not find the {display} channel: {e}")
                return

            # The project channel gets the dashboard and nothing else. Pool
            # management lives on the main admin panel, so there is no second
            # control message here.
            try:
                project_msg = await project_channel.send(
                    embed=self.get_project_embed(project_key),
                    view=ProjectDashboardView(self, project_key))
                self.set_project_ids(project_key, channel_id=project_channel.id, message_id=project_msg.id)
                await message.channel.send(f"✅ {display} dashboard deployed to {project_channel.mention}")
            except Exception as e:
                await message.channel.send(f"❌ Failed to post the {display} dashboard: {e}")

            save_config(self.config)
            return

        # Setup Command
        if cmd.startswith('!filament setup'):
            if not message.author.guild_permissions.administrator:
                await message.channel.send("❌ Admin permissions required.")
                return

            # Read Channels from .env
            pub_env_id = os.getenv('FILAMENT_PUBLIC_CHANNEL_ID')
            admin_env_id = os.getenv('FILAMENT_ADMIN_CHANNEL_ID')

            if not pub_env_id or not admin_env_id:
                await message.channel.send("❌ Missing `FILAMENT_PUBLIC_CHANNEL_ID` or `FILAMENT_ADMIN_CHANNEL_ID` in `.env`.")
                return

            try:
                pub_channel = await self.fetch_channel(int(pub_env_id))
                admin_channel = await self.fetch_channel(int(admin_env_id))
            except Exception as e:
                await message.channel.send(f"❌ Could not find channels: {e}")
                return

            # Post Public Dashboard
            try:
                pub_msg = await pub_channel.send(embed=self.get_public_embed(), view=PublicDashboardView(self))
                self.config['public_channel_id'] = pub_channel.id
                self.config['public_message_id'] = pub_msg.id
                await message.channel.send(f"✅ Public Dashboard deployed to {pub_channel.mention}")
            except Exception as e:
                await message.channel.send(f"❌ Failed to post Public Dashboard: {e}")

            # Post Admin Dashboard
            try:
                # Check if we already have one to avoid spamming admin channel? 
                # For now just post a new one.
                admin_msg = await admin_channel.send(embed=self.get_admin_embed(), view=AdminDashboardView(self))
                self.config['admin_channel_id'] = admin_channel.id
                self.config['admin_message_id'] = admin_msg.id
                await message.channel.send(f"✅ Admin Dashboard deployed to {admin_channel.mention}")
            except Exception as e:
                await message.channel.send(f"❌ Failed to post Admin Dashboard: {e}")

            save_config(self.config)

        # Auto-Clear Messages in the tracked channels
        # Ignore messages from the bot itself (handled above) and never delete a
        # dashboard message, which is identified by its stored message id.
        keep_ids = set()
        tracked_channels = set()

        public_channel_id = self.config.get('public_channel_id')
        if public_channel_id:
            tracked_channels.add(int(public_channel_id))
            if self.config.get('public_message_id'):
                keep_ids.add(int(self.config['public_message_id']))

        # Project channels are kept clean the same way, with each project's
        # dashboard and pool controls protected from deletion.
        for key in PROJECTS:
            ids = self.project_ids(key)
            if ids.get('channel_id'):
                tracked_channels.add(int(ids['channel_id']))
                for id_key in ('message_id', 'admin_message_id'):
                    if ids.get(id_key):
                        keep_ids.add(int(ids[id_key]))

        if message.channel.id in tracked_channels:
            if message.id in keep_ids:
                return

            # Never delete another bot's message. The stream bot posts a live
            # printer feed into a project channel, and this cleanup must not eat
            # it. Human chatter is still cleared.
            if getattr(message.author, 'bot', False):
                return

            # Delete user messages to keep the channel clean
            try:
                await message.delete(delay=1) # Small delay to ensure it's processed
            except:
                pass
