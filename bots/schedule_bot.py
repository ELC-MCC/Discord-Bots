import discord
from discord import ui
import json
import os
import asyncio
from typing import Dict, Optional
import bot_config

# --- Interactive Components ---

class ScheduleModal(ui.Modal, title="Edit Weekly Schedule"):
    monday = ui.TextInput(label="Monday", style=discord.TextStyle.paragraph, placeholder="10:00 AM - 5:00 PM: Open Build", required=False, max_length=1000)
    tuesday = ui.TextInput(label="Tuesday", style=discord.TextStyle.paragraph, placeholder="10:00 AM - 5:00 PM: Open Build", required=False, max_length=1000)
    wednesday = ui.TextInput(label="Wednesday", style=discord.TextStyle.paragraph, placeholder="10:00 AM - 5:00 PM: Open Build", required=False, max_length=1000)
    thursday = ui.TextInput(label="Thursday", style=discord.TextStyle.paragraph, placeholder="10:00 AM - 5:00 PM: Open Build", required=False, max_length=1000)
    friday = ui.TextInput(label="Friday", style=discord.TextStyle.paragraph, placeholder="10:00 AM - 5:00 PM: Open Build", required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        bot: 'ScheduleBot' = interaction.client
        
        # Update Schedule Data
        bot.schedule_data['schedule'] = {
            'Monday': self.monday.value or "Closed",
            'Tuesday': self.tuesday.value or "Closed",
            'Wednesday': self.wednesday.value or "Closed",
            'Thursday': self.thursday.value or "Closed",
            'Friday': self.friday.value or "Closed"
        }
        bot.save_schedule()
        
        await interaction.response.send_message("Schedule updated successfully!", ephemeral=True)
        await bot.update_schedule_display()

        await bot.update_schedule_display()

class ScheduleAdminView(ui.View):
    def __init__(self, bot: 'ScheduleBot'):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Edit Weekly Schedule", style=discord.ButtonStyle.primary, custom_id="schedule_admin_edit")
    async def edit_button(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only Admins can edit the schedule.", ephemeral=True)
            return
        
        modal = ScheduleModal()
        # Pre-fill with current data
        current_schedule = self.bot.schedule_data.get('schedule', {})
        modal.monday.default = current_schedule.get('Monday', '')
        modal.tuesday.default = current_schedule.get('Tuesday', '')
        modal.wednesday.default = current_schedule.get('Wednesday', '')
        modal.thursday.default = current_schedule.get('Thursday', '')
        modal.friday.default = current_schedule.get('Friday', '')
        await interaction.response.send_modal(modal)

class ScheduleBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.schedule_file = "schedule.json"
        self.schedule_data = self.load_schedule()

    def load_schedule(self) -> Dict:
        if not os.path.exists(self.schedule_file):
            return {
                'schedule': {
                    'Monday': "Closed",
                    'Tuesday': "Closed",
                    'Wednesday': "Closed",
                    'Thursday': "Closed",
                    'Friday': "Closed"
                },
                'display_channel_id': None
            }
        try:
            with open(self.schedule_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
             return {
                'schedule': {
                    'Monday': "Closed",
                    'Tuesday': "Closed",
                    'Wednesday': "Closed",
                    'Thursday': "Closed",
                    'Friday': "Closed"
                },
                'display_channel_id': None
            }

    def save_schedule(self):
        with open(self.schedule_file, 'w') as f:
            json.dump(self.schedule_data, f, indent=4)

    async def setup_hook(self):
        self.add_view(ScheduleAdminView(self))

    async def setup_hook(self):
        self.add_view(ScheduleAdminView(self))

    async def on_ready(self):
        print(f'{bot_config.SCHEDULE_BOT_NICKNAME} logged in as {self.user} (ID: {self.user.id})')
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.SCHEDULE_BOT_NICKNAME)
            except Exception as e:
                print(f"Nickname change failed in {guild.name}: {e}")

    async def update_schedule_display(self):
        channel_id = self.schedule_data.get('display_channel_id')
        if not channel_id:
            return

        channel = self.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(channel_id)
            except:
                print(f"Could not find channel with ID {channel_id}")
                return

        # Clear Channel
        try:
            await channel.purge()
        except Exception as e:
            print(f"Failed to purge channel: {e}")

        # Create Embed
        embed = discord.Embed(
            title="Weekly Makerspace Schedule",
            description="Here is the schedule for this week!",
            color=0x9B59B6 # Purple/Magenta for 'fun' without emojis
        )

        schedule = self.schedule_data.get('schedule', {})
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        for day in days:
            times = schedule.get(day, "Closed")
            embed.add_field(name=day, value=times, inline=False)
        
        embed.set_footer(text=bot_config.SCHEDULE_BOT_FOOTER)
        
        await channel.send(embed=embed)

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
             await asyncio.sleep(2)

             embed = discord.Embed(
                 title="The Timekeeper (Schedule Bot)",
                 description="Manages the weekly schedule.\n\n**Usage:**\n• Click **Edit Weekly Schedule** to update open hours.\n• Use `!set_schedule_channel` in the target channel to set where the public schedule appears.",
                 color=0x9B59B6
             )
             await message.channel.send(embed=embed, view=ScheduleAdminView(self))
             return

        # Command: !set_schedule_channel
        if message.content.startswith('!set_schedule_channel'):
            if not message.author.guild_permissions.administrator:
                await message.channel.send("You need Administrator permissions to use this command.")
                return

            self.schedule_data['display_channel_id'] = message.channel.id
            self.save_schedule()
            await message.channel.send(f"Schedule display channel set to {message.channel.mention}")
            await self.update_schedule_display() # Initial update

        # Command: !setup_schedule (Spawns the Edit Button)
        if message.content.startswith('!setup_schedule'):
            if not message.author.guild_permissions.administrator:
                await message.channel.send("You need Administrator permissions to use this command.")
                return

            view = ui.View()
            button = ui.Button(label="Edit Weekly Schedule", style=discord.ButtonStyle.primary)

            async def edit_button_callback(interaction):
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message("Only Admins can edit the schedule.", ephemeral=True)
                    return
                
                modal = ScheduleModal()
                # Pre-fill with current data
                current_schedule = self.schedule_data.get('schedule', {})
                modal.monday.default = current_schedule.get('Monday', '')
                modal.tuesday.default = current_schedule.get('Tuesday', '')
                modal.wednesday.default = current_schedule.get('Wednesday', '')
                modal.thursday.default = current_schedule.get('Thursday', '')
                modal.friday.default = current_schedule.get('Friday', '')

                await interaction.response.send_modal(modal)

            button.callback = edit_button_callback
            view.add_item(button)
            await message.channel.send("Use the button below to update the schedule:", view=view)
