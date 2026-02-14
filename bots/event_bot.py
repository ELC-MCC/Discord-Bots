import discord
from discord import ui
import json
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import bot_config

# --- Interactive Components ---

class EventModal(ui.Modal, title="Add New Event"):
    name = ui.TextInput(label="Event Name", placeholder="Movie Night", max_length=100)
    date_str = ui.TextInput(label="Date (YYYY-MM-DD)", placeholder="2024-12-25", min_length=10, max_length=10)
    time_str = ui.TextInput(label="Time (HH:MM)", placeholder="20:00", min_length=5, max_length=5)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Watch movies together...", required=False, max_length=1000)
    image_url = ui.TextInput(label="Image URL", placeholder="https://example.com/image.png", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate Date/Time
        full_time_str = f"{self.date_str.value} {self.time_str.value}"
        try:
            datetime.strptime(full_time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            await interaction.response.send_message(
                "Error: Invalid Date/Time Format. Use YYYY-MM-DD for date and HH:MM (24-hour) for time.", 
                ephemeral=True
            )
            return

        # Create Event Object
        new_event = {
            "name": self.name.value,
            "time": full_time_str,
            "description": self.description.value,
            "image_url": self.image_url.value if self.image_url.value else None,
            "created_by": interaction.user.id
        }

        # Access Bot Instance
        bot: 'EventBot' = interaction.client
        bot.events.append(new_event)
        bot.save_events()
        
        await bot.update_dashboard()
        await interaction.response.send_message(f"Event **{self.name.value}** allocated for {full_time_str}.", ephemeral=True)
        print(f"Event added via Modal: {self.name.value}")

class DeleteEventSelect(ui.Select):
    def __init__(self, events: List[Dict]):
        options = []
        # Sort events by time for the list
        sorted_events = sorted(events, key=lambda x: x['time'])
        for i, event in enumerate(sorted_events):
            # Value must be string, utilizing index or unique ID if we had one. 
            # Using index of sorted list is risky if list changes, but reasonably safe for ephemeral interaction.
            # Better: Use the raw index from the main list, or just pass the event data.
            # Let's map the option value to the index in the MAIN list.
            try:
                original_index = events.index(event)
                label = f"{event['time']} - {event['name']}"
                if len(label) > 100: label = label[:97] + "..."
                options.append(discord.SelectOption(label=label, value=str(original_index)))
            except ValueError:
                continue
        
        if not options:
            options.append(discord.SelectOption(label="No events to delete", value="-1"))

        super().__init__(placeholder="Select an event to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        if index == -1:
            await interaction.response.send_message("No event selected.", ephemeral=True)
            return

        bot: 'EventBot' = interaction.client
        if 0 <= index < len(bot.events):
            removed_event = bot.events.pop(index)
            bot.save_events()
            await bot.update_dashboard()
            await interaction.response.send_message(f"Deleted event: **{removed_event['name']}**", ephemeral=True)
        else:
            await interaction.response.send_message("Event not found (it might have already been deleted).", ephemeral=True)

class DeleteEventView(ui.View):
    def __init__(self, events: List[Dict]):
        super().__init__()
        self.add_item(DeleteEventSelect(events))

class DashboardView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent View

    @ui.button(label="Add Event", style=discord.ButtonStyle.green, custom_id="event_bot:add_event")
    async def add_event(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(EventModal())

    @ui.button(label="Delete Event", style=discord.ButtonStyle.red, custom_id="event_bot:delete_event")
    async def delete_event(self, interaction: discord.Interaction, button: ui.Button):
        bot: 'EventBot' = interaction.client
        if not bot.events:
             await interaction.response.send_message("No events to delete.", ephemeral=True)
             return
        await interaction.response.send_message("Select an event to remove:", view=DeleteEventView(bot.events), ephemeral=True)
    
    @ui.button(label="Refresh", style=discord.ButtonStyle.gray, custom_id="event_bot:refresh")
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        bot: 'EventBot' = interaction.client
        await bot.update_dashboard()
        await interaction.response.send_message("Dashboard refreshed.", ephemeral=True)

# --- Main Bot Class ---

class EventBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events_file = "events.json"
        self.data = self.load_data()
        self.events = self.data['events']
        self.bg_task = None
        self.channel_id = None

    def load_data(self) -> Dict:
        if not os.path.exists(self.events_file):
            return {'events': [], 'dashboard': None}
        try:
            with open(self.events_file, 'r') as f:
                content = json.load(f)
                if isinstance(content, list):
                    return {'events': content, 'dashboard': None}
                return content
        except json.JSONDecodeError:
            return {'events': [], 'dashboard': None}

    def save_events(self):
        with open(self.events_file, 'w') as f:
            json.dump(self.data, f, indent=4)

    async def setup_hook(self):
        # Register the persistent view so interactions work after restart
        self.add_view(DashboardView())

    async def on_ready(self):
        print(f'The Event Loop logged in as {self.user} (ID: {self.user.id})')
        
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.EVENT_BOT_NICKNAME)
            except Exception as e:
                print(f"Nickname change failed in {guild.name}: {e}")

        try:
            self.channel_id = int(os.getenv('EVENT_CHANNEL_ID', '0'))
        except ValueError:
            self.channel_id = 0

        if not self.bg_task:
            self.bg_task = self.loop.create_task(self.check_events())

    async def check_events(self):
        await self.wait_until_ready()
        print("The Event Loop background task started.")
        while not self.is_closed():
            now = datetime.now()
            events_to_remove = []
            
            for event in self.events:
                try:
                    event_time = datetime.strptime(event['time'], "%Y-%m-%d %H:%M")
                    if now >= event_time:
                        channel = self.get_channel(self.channel_id)
                        if channel:
                            embed = discord.Embed(
                                title=f"Event Starting: {event['name']}",
                                description=event['description'],
                                color=0x2ECC71,
                                timestamp=now
                            )
                            if event.get('image_url'):
                                embed.set_image(url=event['image_url'])
                            embed.set_footer(text=bot_config.EVENT_BOT_FOOTER)
                            await channel.send(f"@everyone Event is starting now!", embed=embed)
                            print(f"Triggered event: {event['name']}")
                        
                        events_to_remove.append(event)
                except ValueError:
                    events_to_remove.append(event)

            if events_to_remove:
                for e in events_to_remove:
                    if e in self.events:
                        self.events.remove(e)
                self.save_events()
                await self.update_dashboard()

            await asyncio.sleep(60)

    async def update_dashboard(self):
        """Updates the persistent dashboard message."""
        dashboard_data = self.data.get('dashboard')
        if not dashboard_data:
            return

        channel_id = dashboard_data.get('channel_id')
        message_id = dashboard_data.get('message_id')
        
        if not channel_id or not message_id:
            return

        try:
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
            
            embed = discord.Embed(title="📅 Upcoming Events", color=0x3498DB)
            if not self.events:
                embed.description = "No events scheduled."
                embed.color = 0x95A5A6
            else:
                sorted_events = sorted(self.events, key=lambda x: x['time'])
                for event in sorted_events:
                    # Parse time to nicer format if possible, but keeping it raw is safer for now
                    embed.add_field(
                        name=f"{event['time']} | {event['name']}",
                        value=event['description'] or "No description",
                        inline=False
                    )
            
            embed.set_footer(text=f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Attach the persistent view!
            await message.edit(embed=embed, view=DashboardView())
            
        except discord.NotFound:
            print("Dashboard missing. Removing config.")
            self.data['dashboard'] = None
            self.save_events()
        except Exception as e:
            print(f"Failed to update dashboard: {e}")

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Setup Command
        if message.content.startswith('!setup_dashboard'):
            try:
                # Post the initial message
                embed = discord.Embed(title="📅 Upcoming Events", description="Initializing...", color=0x3498DB)
                dashboard_msg = await message.channel.send(embed=embed, view=DashboardView())
                
                # Save config
                self.data['dashboard'] = {
                    'channel_id': message.channel.id,
                    'message_id': dashboard_msg.id
                }
                self.save_events()
                await self.update_dashboard()
                
                await message.delete() # Clean up command
                print(f"Dashboard initialized in {message.channel.name}")

            except Exception as e:
                await message.channel.send(f"Error setting up dashboard: {e}")

