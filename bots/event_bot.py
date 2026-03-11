import discord
from discord import ui
import json
import os
import asyncio
import calendar
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import bot_config

# --- Interactive Components ---

class EventModal(ui.Modal, title="Add New Event"):
    name = ui.TextInput(label="Event Name", placeholder="Movie Night", max_length=100)
    date_str = ui.TextInput(label="Date (YYYY-MM-DD)", placeholder="2024-12-25", min_length=10, max_length=10)
    time_str = ui.TextInput(label="Time (HH:MM)", placeholder="20:00", min_length=5, max_length=5)
    location = ui.TextInput(label="Location", placeholder="Main Hall", required=True, max_length=100)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Watch movies together...", required=False, max_length=1000)

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

        # Ack the modal first to avoid timeout, but we need to send a follow-up for the image
        await interaction.response.send_message(
            f"Event details for **{self.name.value}** recorded.\n"
            "**Please upload an image for the event now.**\n"
            "*(Reply with an image attachment, or type `skip` to proceed without one)*",
            ephemeral=True
        )

        bot: 'EventBot' = interaction.client
        
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        image_url = None
        try:
            # Wait for image upload
            msg = await bot.wait_for('message', check=check, timeout=60.0)
            
            if msg.attachments:
                image_url = msg.attachments[0].url
                await interaction.followup.send("Image received! (Message kept to preserve image link)", ephemeral=True)
            elif msg.content.lower().strip() == 'skip':
                await interaction.followup.send("Skipping image upload.", ephemeral=True)
                # Try to delete the 'skip' message to keep chat clean
                try:
                    await msg.delete()
                except:
                    pass
            else:
                await interaction.followup.send("No image found in message. Proceeding without image.", ephemeral=True)
                try:
                    await msg.delete()
                except:
                    pass

        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for image. Event created without one.", ephemeral=True)

        # Create Event Object
        new_event = {
            "name": self.name.value,
            "time": full_time_str,
            "location": self.location.value,
            "description": self.description.value,
            "image_url": image_url,
            "created_by": interaction.user.id
        }

        bot.events.append(new_event)
        bot.save_events()
        
        print(f"Event added via Modal: {self.name.value}")

class RecurringEventModal(ui.Modal, title="Add Recurring Event"):
    name = ui.TextInput(label="Event Name", placeholder="Weekly Meeting", max_length=100)
    day_of_week = ui.TextInput(label="Day of Week", placeholder="Monday", max_length=10)
    time_str = ui.TextInput(label="Time (HH:MM)", placeholder="18:00", min_length=5, max_length=5)
    location = ui.TextInput(label="Location", placeholder="Main Hall", required=True, max_length=100)
    description = ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Every week...", required=False, max_length=1000)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            datetime.strptime(self.time_str.value, "%H:%M")
        except ValueError:
            await interaction.response.send_message("Invalid Time Format. Use HH:MM (24-hour).", ephemeral=True)
            return
            
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if self.day_of_week.value.lower() not in days:
            await interaction.response.send_message("Invalid Day of Week. Please use full names (e.g. Monday).", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Recurring event details for **{self.name.value}** recorded.\n"
            "**Please upload an image for the event now.**\n"
            "*(Reply with an image attachment, or type `skip` to proceed without one)*",
            ephemeral=True
        )

        bot: 'EventBot' = interaction.client
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        image_url = None
        try:
            msg = await bot.wait_for('message', check=check, timeout=60.0)
            if msg.attachments:
                image_url = msg.attachments[0].url
                await interaction.followup.send("Image received!", ephemeral=True)
            elif msg.content.lower().strip() == 'skip':
                await interaction.followup.send("Skipping image upload.", ephemeral=True)
                try: await msg.delete()
                except: pass
            else:
                await interaction.followup.send("No image found. Proceeding without.", ephemeral=True)
                try: await msg.delete()
                except: pass
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out waiting for image. Event created without one.", ephemeral=True)

        new_event = {
            "type": "recurring",
            "name": self.name.value,
            "day_of_week": self.day_of_week.value.capitalize(),
            "time": self.time_str.value,
            "location": self.location.value,
            "description": self.description.value,
            "image_url": image_url,
            "created_by": interaction.user.id,
            "last_triggered": None
        }

        bot.events.append(new_event)
        bot.save_events()
        
        print(f"Recurring Event added via Modal: {self.name.value}")

class EventBot(discord.Client):
    pass # Type hinting for circular reference

class DeleteEventSelect(ui.Select):
    def __init__(self, events: List[Dict], bot: 'EventBot'):
        self.bot = bot
        options = []
        # Sort events by time and store them so we can access by index later
        self.sorted_events = sorted(events, key=lambda x: x['time'])
        
        for i, event in enumerate(self.sorted_events):
            # Use index as value to ensure uniqueness and short length
            value = str(i)
            
            if event.get("type") == "recurring":
                label = f"Every {event.get('day_of_week')} {event['time']} - {event['name']}"
            else:
                label = f"{event['time']} - {event['name']}"
                
            if len(label) > 100: label = label[:97] + "..."

            options.append(discord.SelectOption(label=label, value=value))
            
            if len(options) >= 25: break # Discord limit

        super().__init__(placeholder="Select an event to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            index = int(self.values[0])
            if 0 <= index < len(self.sorted_events):
                event_to_remove = self.sorted_events[index]
                
                if event_to_remove in self.bot.events:
                    self.bot.events.remove(event_to_remove)
                    self.bot.save_events()
                    await interaction.response.send_message(f"Event **{event_to_remove['name']}** deleted.", ephemeral=True)
                    print(f"Deleted event: {event_to_remove['name']}")
                else:
                     await interaction.response.send_message("Event not found (maybe already deleted).", ephemeral=True)
            else:
                await interaction.response.send_message("Invalid selection.", ephemeral=True)
        except Exception as e:
            print(f"Error in delete callback: {e}")
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

class DeleteEventView(ui.View):
    def __init__(self, events: List[Dict], bot: 'EventBot'):
        super().__init__()
        self.add_item(DeleteEventSelect(events, bot))

class CalendarView(ui.View):
    def __init__(self, bot: 'EventBot', year: int, month: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.year = year
        self.month = month
        self.build_view()

    def get_month_events(self):
        month_events = []
        for i, event in enumerate(self.bot.events):
            if event.get("type") == "recurring":
                day_name = event.get("day_of_week")
                time_str = event["time"]
                try:
                    time_obj = datetime.strptime(time_str, "%H:%M").time()
                    cal = calendar.Calendar()
                    days_in_month = [d for d in cal.itermonthdates(self.year, self.month) if d.month == self.month]
                    for d in days_in_month:
                        if d.strftime("%A") == day_name:
                            dt = datetime.combine(d, time_obj)
                            month_events.append((i, dt, event))
                except Exception:
                    pass
            else:
                try:
                    dt = datetime.strptime(event['time'], "%Y-%m-%d %H:%M")
                    if dt.year == self.year and dt.month == self.month:
                        month_events.append((i, dt, event))
                except ValueError:
                    pass
        month_events.sort(key=lambda x: x[1])
        return month_events

    def get_embed(self) -> discord.Embed:
        month_name = calendar.month_name[self.month]
        embed = discord.Embed(title=f"🗓️ Events Calendar - {month_name} {self.year}", color=0x3498DB)
        
        month_events = self.get_month_events()
        
        if not month_events:
            embed.description = "No events scheduled for this month."
        else:
            description = ""
            for _, dt, event in month_events:
                day_str = dt.strftime("%b %d")
                time_str = dt.strftime("%I:%M %p")
                prefix = "🔁 " if event.get("type") == "recurring" else ""
                description += f"• **{day_str}** at {time_str}: **{prefix}{event['name']}**\n"
            
            embed.description = description
            
        return embed

    def build_view(self):
        self.clear_items()
        
        # Prev / Next
        prev_btn = ui.Button(label="◀️ Prev Month", style=discord.ButtonStyle.secondary)
        async def prev_callback(inter: discord.Interaction):
            self.month -= 1
            if self.month < 1:
                self.month = 12
                self.year -= 1
            self.build_view()
            await inter.response.edit_message(embed=self.get_embed(), view=self)
        prev_btn.callback = prev_callback
        self.add_item(prev_btn)
        
        next_btn = ui.Button(label="Next Month ▶️", style=discord.ButtonStyle.secondary)
        async def next_callback(inter: discord.Interaction):
            self.month += 1
            if self.month > 12:
                self.month = 1
                self.year += 1
            self.build_view()
            await inter.response.edit_message(embed=self.get_embed(), view=self)
        next_btn.callback = next_callback
        self.add_item(next_btn)

        # Select Menu
        month_events = self.get_month_events()
        if month_events:
            options = []
            for i, dt, event in month_events:
                label = f"{dt.strftime('%b %d')} - {event['name']}"
                if len(label) > 100: label = label[:97] + "..."
                options.append(discord.SelectOption(label=label, value=str(i)))
                if len(options) >= 25: break
                
            select = ui.Select(placeholder="Select an event for details...", options=options)
            
            async def select_callback(inter: discord.Interaction):
                event_idx = int(select.values[0])
                if 0 <= event_idx < len(self.bot.events):
                    ev = self.bot.events[event_idx]
                    if ev.get("type") == "recurring":
                        detail_embed = discord.Embed(
                            title=f"🔁 {ev['name']}",
                            description=f"**Every {ev.get('day_of_week')}** at **{ev.get('time')}**\n"
                                        f"Location: **{ev.get('location', 'No location')}**\n\n"
                                        f"{ev.get('description', '')}",
                            color=0x9B59B6
                        )
                    else:
                        dt = datetime.strptime(ev['time'], "%Y-%m-%d %H:%M")
                        detail_embed = discord.Embed(
                            title=ev['name'],
                            description=f"**{dt.strftime('%A, %B %d, %Y')}** at **{dt.strftime('%I:%M %p')}**\n"
                                        f"Location: **{ev.get('location', 'No location')}**\n\n"
                                        f"{ev.get('description', '')}",
                            color=0x2ECC71
                        )
                    if ev.get('image_url'):
                        detail_embed.set_image(url=ev['image_url'])
                    await inter.response.send_message(embed=detail_embed, ephemeral=True)
                else:
                    await inter.response.send_message("Event not found.", ephemeral=True)
                    
            select.callback = select_callback
            self.add_item(select)

class CalendarLauncher(ui.View):
    def __init__(self, bot: 'EventBot'):
        super().__init__(timeout=None)
        self.bot = bot
        
    @ui.button(label="🗓️ Open Interactive Calendar", style=discord.ButtonStyle.primary, custom_id="launch_cal_btn")
    async def launch_calendar(self, interaction: discord.Interaction, button: ui.Button):
        now = datetime.now()
        view = CalendarView(self.bot, now.year, now.month)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

class EventAdminView(ui.View):
    def __init__(self, bot: 'EventBot'):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Add Event", style=discord.ButtonStyle.green, custom_id="event_admin_add")
    async def add_event(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(EventModal())

    @ui.button(label="Add Recurring", style=discord.ButtonStyle.secondary, custom_id="event_admin_add_rec")
    async def add_recurring(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(RecurringEventModal())

    @ui.button(label="Delete Event", style=discord.ButtonStyle.red, custom_id="event_admin_del")
    async def delete_event(self, interaction: discord.Interaction, button: ui.Button):
        if not self.bot.events:
            await interaction.response.send_message("No events to delete.", ephemeral=True, delete_after=5)
            return
        del_view = DeleteEventView(self.bot.events, self.bot)
        await interaction.response.send_message("Select an event to delete:", view=del_view, ephemeral=True)

    @ui.button(label="Setup Upcoming", style=discord.ButtonStyle.blurple, custom_id="event_admin_upcoming")
    async def setup_upcoming(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Select the channel for the upcoming events dashboard:", view=UpcomingChannelSelect(self.bot), ephemeral=True)

class UpcomingChannelSelect(ui.View):
    def __init__(self, bot: 'EventBot'):
        super().__init__(timeout=60)
        self.bot = bot

    @ui.select(cls=ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Select a channel...")
    async def select_channel(self, interaction: discord.Interaction, select: ui.ChannelSelect):
        channel = select.values[0]
        
        # Send initial message
        embeds = self.bot.get_upcoming_embeds()
        try:
            msg = await channel.send(embeds=embeds, view=CalendarLauncher(self.bot))
            
            # Store ID
            self.bot.data['upcoming_message_id'] = msg.id
            self.bot.data['upcoming_channel_id'] = msg.channel.id
            self.bot.save_events()
            
            await interaction.response.send_message(f"Upcoming events dashboard created in {channel.mention}", ephemeral=True)
            self.stop()
        except discord.Forbidden:
             await interaction.response.send_message(f"Error: I do not have permission to send messages in {channel.mention}", ephemeral=True)
        except Exception as e:
             await interaction.response.send_message(f"Error setting up dashboard: {e}", ephemeral=True)

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
            return {'events': [], 'upcoming_message_id': None, 'upcoming_channel_id': None}
        try:
            with open(self.events_file, 'r') as f:
                content = json.load(f)
                if isinstance(content, list):
                    return {'events': content}
                return content
        except json.JSONDecodeError:
            return {'events': [], 'upcoming_message_id': None, 'upcoming_channel_id': None}

    def save_events(self):
        with open(self.events_file, 'w') as f:
            json.dump(self.data, f, indent=4)
        # Trigger update when events change
        if hasattr(self, 'loop'):
            self.loop.create_task(self.update_upcoming_message())

    async def setup_hook(self):
        self.add_view(EventAdminView(self))
        self.add_view(CalendarLauncher(self))

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
            
        try:
            self.recurring_channel_id = int(os.getenv('RECURRING_EVENT_CHANNEL_ID', str(self.channel_id)))
        except ValueError:
            self.recurring_channel_id = self.channel_id

        if not self.bg_task:
            self.bg_task = self.loop.create_task(self.check_events())
            
    def get_date_suffix(self, day):
        if 4 <= day <= 20 or 24 <= day <= 30:
            return "th"
        else:
            return ["st", "nd", "rd"][day % 10 - 1]

    def get_upcoming_embeds(self) -> List[discord.Embed]:
        # Filter for future events
        now = datetime.now()
        future_events = []
        for event in self.events:
            if event.get("type") == "recurring":
                try:
                    day_name = event.get("day_of_week")
                    time_obj = datetime.strptime(event["time"], "%H:%M").time()
                    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    target_wd = days.index(day_name)
                    current_wd = now.weekday()
                    
                    days_ahead = target_wd - current_wd
                    if days_ahead < 0:
                        days_ahead += 7
                        
                    next_date = now.date() + timedelta(days=days_ahead)
                    next_dt = datetime.combine(next_date, time_obj)
                    
                    if days_ahead == 0 and next_dt <= now:
                        next_dt += timedelta(days=7)
                        
                    future_events.append((next_dt, event))
                except Exception:
                    continue
            else:
                try:
                    event_time = datetime.strptime(event['time'], "%Y-%m-%d %H:%M")
                    if event_time > now:
                        future_events.append((event_time, event))
                except ValueError:
                    continue
        
        # Sort by time and take top 3
        future_events.sort(key=lambda x: x[0])
        next_events = future_events[:3]

        embeds = []
        
        if not next_events:
            embed = discord.Embed(
                title="Upcoming Events",
                description="No upcoming events scheduled.",
                color=0x95A5A6
            )
            embeds.append(embed)
            return embeds
        
        # Header Embed
        header = discord.Embed(
            title="Upcoming Events",
            description="Here is what is coming up next:",
            color=0x2C3E50
        )
        embeds.append(header)

        for dt, event in next_events:
            # Format: February 5th, 2026
            day = dt.day
            suffix = self.get_date_suffix(day)
            date_str = dt.strftime(f"%B {day}{suffix}, %Y")
            time_str = dt.strftime("%I:%M %p") # 5:00 PM

            title = f"🔁 {event['name']}" if event.get("type") == "recurring" else event['name']
            embed = discord.Embed(
                title=title,
                color=0x9B59B6 if event.get("type") == "recurring" else 0x3498DB
            )
            
            freq_str = f"**Every {event.get('day_of_week')}** at **{time_str}**" if event.get("type") == "recurring" else f"**{date_str}** at **{time_str}**"
            description_text = (
                f"{freq_str}\n"
                f"Location: **{event.get('location', 'No location')}**\n\n"
                f"{event.get('description', '')}"
            )
            
            embed.description = description_text
            
            if event.get('image_url'):
                embed.set_image(url=event['image_url'])
            
            embeds.append(embed)

        # Add footer to the last embed
        embeds[-1].set_footer(text=bot_config.EVENT_BOT_FOOTER)
        embeds[-1].timestamp = now
        
        return embeds

    async def update_upcoming_message(self):
        msg_id = self.data.get('upcoming_message_id')
        chan_id = self.data.get('upcoming_channel_id')
        
        if not msg_id or not chan_id:
            return

        try:
            channel = self.get_channel(chan_id)
            if not channel:
                # Try fetching if not in cache
                try:
                    channel = await self.fetch_channel(chan_id)
                except:
                    return

            try:
                message = await channel.fetch_message(msg_id)
                await message.edit(embeds=self.get_upcoming_embeds(), view=CalendarLauncher(self))
            except discord.NotFound:
                # Message deleted, clear data
                self.data['upcoming_message_id'] = None
                self.data['upcoming_channel_id'] = None
                self.save_events()
            except Exception as e:
                print(f"Failed to update upcoming message: {e}")
                
        except Exception as e:
            print(f"Error in update_upcoming_message: {e}")

    async def check_events(self):
        await self.wait_until_ready()
        print("The Event Loop background task started.")
        while not self.is_closed():
            now = datetime.now()
            events_to_remove = []
            
            for event in self.events:
                if event.get("type") == "recurring":
                    if now.strftime("%A") == event.get("day_of_week") and now.strftime("%H:%M") == event.get("time"):
                        today_str = now.strftime("%Y-%m-%d")
                        if event.get("last_triggered") != today_str:
                            channel = self.get_channel(self.recurring_channel_id)
                            if channel:
                                embed = discord.Embed(
                                    title=f"Recurring Event Starting: {event['name']}",
                                    description=f"Location: **{event.get('location', 'No location')}**\n{event.get('description', '')}",
                                    color=0x9B59B6,
                                    timestamp=now
                                )
                                if event.get('image_url'):
                                    embed.set_image(url=event['image_url'])
                                embed.set_footer(text=bot_config.EVENT_BOT_FOOTER)
                                await channel.send(embed=embed)
                                print(f"Triggered recurring event: {event['name']}")
                            event["last_triggered"] = today_str
                            self.save_events()
                else:
                    try:
                        event_time = datetime.strptime(event['time'], "%Y-%m-%d %H:%M")
                        if now >= event_time:
                            channel = self.get_channel(self.channel_id)
                            if channel:
                                embed = discord.Embed(
                                    title=f"Event Starting: {event['name']}",
                                    description=f"Location: **{event.get('location', 'No location')}**\n{event.get('description', '')}",
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
                # Update the upcoming events message since events were removed
                await self.update_upcoming_message()

            # Periodic update to keeping "Time until" or just refresh the list if an event passed without notification logic triggering yet
            # Also ensures the "Next 3" rotates if one finished
            if now.second < 5: # Just do it once a minute roughly
                 await self.update_upcoming_message()

            await asyncio.sleep(60)

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
                 title="The Event Loop (Event Bot)",
                 description="Manages community events.\n\n**Usage:**\n• **Add Event**: Create a new event listing.\n• **Delete Event**: Remove an existing event.\n• Use `!setup_upcoming` in the target channel to spawn the live dashboard.",
                 color=0x2ECC71
             )
             await message.channel.send(embed=embed, view=EventAdminView(self))
             return

        # Setup Command - Add Event via Modal
        if message.content.startswith('!add_event'):
             if not message.author.guild_permissions.administrator:
                 await message.channel.send("You need Administrator permissions to use this command.")
                 return

             view = ui.View()
             button = ui.Button(label="Add Event", style=discord.ButtonStyle.green)
             
             async def button_callback(interaction):
                 await interaction.response.send_modal(EventModal())
             
             button.callback = button_callback
             view.add_item(button)
             await message.channel.send("Click to add an event:", view=view)

        # Command: !upcoming
        if message.content.startswith('!upcoming'):
            embeds = self.get_upcoming_embeds()
            await message.channel.send(embeds=embeds, view=CalendarLauncher(self))

        # Command: !list_events (Lists ALL events via Interactive Calendar)
        if message.content.startswith('!list_events'):
            now = datetime.now()
            view = CalendarView(self, now.year, now.month)
            await message.channel.send(embed=view.get_embed(), view=view)

        # Command: !delete_event (Admin Access)
        if message.content.startswith('!delete_event'):
            if not message.author.guild_permissions.administrator:
                await message.channel.send("You need Administrator permissions to use this command.")
                return

            view = ui.View()
            button = ui.Button(label="Delete Event", style=discord.ButtonStyle.red)

            async def delete_button_callback(interaction):
                try:
                    if not interaction.user.guild_permissions.administrator:
                         await interaction.response.send_message("You need Administrator permissions to use this button.", ephemeral=True)
                         return

                    if not self.events:
                        await interaction.response.send_message("No events to delete.", ephemeral=True)
                        return

                    # Create the select view dynamically to get the latest events
                    del_view = DeleteEventView(self.events, self)
                    await interaction.response.send_message("Select an event to delete:", view=del_view, ephemeral=True)
                except Exception as e:
                    print(f"Error in delete_button_callback: {e}")
                    await interaction.response.send_message("An error occurred while opening the menu.", ephemeral=True)

            button.callback = delete_button_callback
            view.add_item(button)
            await message.channel.send("Click to delete an event:", view=view)

        # Command: !setup_upcoming (Admin Only)
        if message.content.startswith('!setup_upcoming'):
             if not message.author.guild_permissions.administrator:
                await message.channel.send("You need Administrator permissions to setup the upcoming events dashboard.")
                return
            
             # Send initial message
             embeds = self.get_upcoming_embeds()
             msg = await message.channel.send(embeds=embeds, view=CalendarLauncher(self))
             
             # Store ID
             self.data['upcoming_message_id'] = msg.id
             self.data['upcoming_channel_id'] = msg.channel.id
             self.save_events()
             
             # Delete command message to keep it clean
             try:
                 await message.delete()
             except:
                 pass

