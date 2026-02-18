import discord
from discord import ui
from discord.ext import tasks
import os
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

# --- Modals ---
class LogUsageModal(ui.Modal, title="Log Filament Usage"):
    first_name = ui.TextInput(label="First Name", placeholder="Enter your name", min_length=1, max_length=50)
    amount = ui.TextInput(label="Amount Used (g)", placeholder="e.g. 50.5", min_length=1, max_length=10)

    def __init__(self, bot, filament_id, filament_name):
        super().__init__()
        self.bot = bot
        self.filament_id = filament_id
        self.filament_name = filament_name

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount_val = float(self.amount.value)
            
            # Combine name and user for logging
            user_display = f"{self.first_name.value} ({interaction.user.display_name})"
            
            self.bot.data_manager.log_usage(user_display, self.filament_id, amount_val)
            self.bot.data_manager.update_filament_weight(self.filament_id, amount_val)
            
            # Send a regular message that auto-deletes instead of ephemeral
            await interaction.response.send_message(
                f"Logged **{amount_val}g** usage for **{self.filament_name}** by **{self.first_name.value}**.",
                delete_after=5
            )
            # Trigger dashboard updates
            await self.bot.update_dashboards()
            
        except ValueError:
            await interaction.response.send_message("Invalid amount. Please enter a number.", delete_after=5)
        except Exception as e:
            print(f"Error logging usage: {e}")
            await interaction.response.send_message(f"An error occurred: {e}", delete_after=5)

class AddFilamentModal(ui.Modal, title="Add New Filament"):
    brand = ui.TextInput(label="Brand", placeholder="e.g., Elegoo", max_length=50)
    type_name = ui.TextInput(label="Type", placeholder="e.g., PLA", max_length=20)
    color = ui.TextInput(label="Color", placeholder="e.g., Matte Black", max_length=30)
    weight = ui.TextInput(label="Initial Weight (g)", placeholder="e.g., 1000", max_length=10)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        try:
            weight_val = float(self.weight.value)
            new_id = self.bot.data_manager.add_inventory_item(
                self.type_name.value, 
                self.brand.value, 
                self.color.value, 
                weight_val
            )
            await interaction.response.send_message(
                f"Added **{self.brand.value} {self.type_name.value} ({self.color.value})** with ID **{new_id}**.",
                delete_after=5
            )
            await self.bot.update_dashboards()
            
        except ValueError:
             await interaction.response.send_message("❌ Invalid weight. Please enter a number.", ephemeral=True)
        except Exception as e:
            print(f"Error adding filament: {e}")
            await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)

# --- Select Menus ---
class FilamentSelect(ui.Select):
    def __init__(self, bot):
        self.bot: 'FilamentBot' = bot
        options = []
        inventory = self.bot.data_manager.get_inventory()
        sorted_inv = sorted(inventory, key=lambda x: (x.get('type', ''), x.get('color', '')))
        
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

        super().__init__(placeholder="Select a filament...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        filament_id = int(self.values[0])
        inventory = self.bot.data_manager.get_inventory()
        item = next((x for x in inventory if x['id'] == filament_id), None)
        name = f"{item['color']} {item['type']}" if item else "Unknown"
        
        await interaction.response.send_modal(LogUsageModal(self.bot, filament_id, name))

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

    @ui.button(label="Add Filament", style=discord.ButtonStyle.primary, custom_id="filament_admin_add")
    async def add_filament_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(AddFilamentModal(self.bot))

    @ui.button(label="Export Logs", style=discord.ButtonStyle.secondary, custom_id="filament_admin_export")
    async def export_logs_btn(self, interaction: discord.Interaction, button: ui.Button):
        csv_data = self.bot.data_manager.export_logs_to_csv()
        
        # Create a temporary file to send
        import io
        file = discord.File(io.StringIO(csv_data), filename="filament_logs_export.csv")
        
        await interaction.response.send_message("📊 Here is the latest usage log:", file=file, ephemeral=True)

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
            f"Monthly Used: {stats['monthly']}g"
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
                    content += f"{item['brand']} {item['color']}: {item['weight_g']}g\n"
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
            
            # Post Admin Dashboard
            try:
                # We use the existing get_admin_embed and AdminDashboardView
                await message.channel.send(embed=self.get_admin_embed(), view=AdminDashboardView(self))
            except Exception as e:
                print(f"FilamentBot failed to post admin setup: {e}")
            return

        # Setup Command
        if message.content.startswith('!filament setup'):
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

        # Auto-Clear Messages in Public Channel
        # Ignore messages from the bot itself (unless we want to clean up its own responses, 
        # but we handle those with delete_after)
        # AND ignore the dashboard message if it somehow triggers this
        
        public_channel_id = self.config.get('public_channel_id')
        if public_channel_id and message.channel.id == int(public_channel_id):
             # Don't delete the dashboard message
            public_msg_id = self.config.get('public_message_id')
            if public_msg_id and message.id == int(public_msg_id):
                return
            
            # Delete user messages to keep channel clean
            try:
                await message.delete(delay=1) # Small delay to ensure it's processed
            except:
                pass
