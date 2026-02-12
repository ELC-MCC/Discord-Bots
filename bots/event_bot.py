import discord
import json
import os
import asyncio
from datetime import datetime
from typing import List, Dict
import bot_config

class EventBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events_file = "events.json"
        self.events: List[Dict] = self.load_events()
        self.bg_task = None
        self.channel_id = None

    def load_events(self) -> List[Dict]:
        if not os.path.exists(self.events_file):
            return []
        try:
            with open(self.events_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def save_events(self):
        with open(self.events_file, 'w') as f:
            json.dump(self.events, f, indent=4)

    async def on_ready(self):
        print(f'The Event Loop logged in as {self.user} (ID: {self.user.id})')
        
        # Set nickname
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.EVENT_BOT_NICKNAME)
                print(f"Changed nickname to '{bot_config.EVENT_BOT_NICKNAME}' in {guild.name}")
            except Exception as e:
                print(f"Nickname change failed in {guild.name}: {e}")

        # Load Channel ID from env
        try:
            self.channel_id = int(os.getenv('EVENT_CHANNEL_ID', '0'))
        except ValueError:
            print("Error: EVENT_CHANNEL_ID is not a valid integer.")
            self.channel_id = 0

        # Start background task if not already running
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
                    
                    # Check if event time has arrived (or acted upon within a reasonable window, e.g. 1 minute grace)
                    # We check if (now >= event_time)
                    if now >= event_time:
                        channel = self.get_channel(self.channel_id)
                        if channel:
                            embed = discord.Embed(
                                title=f"Event Starting: {event['name']}",
                                description=event['description'],
                                color=0x2ECC71, # Green
                                timestamp=now
                            )
                            if event.get('image_url'):
                                embed.set_image(url=event['image_url'])
                            embed.set_footer(text=bot_config.EVENT_BOT_FOOTER)
                            await channel.send(f"@everyone Event is starting now!", embed=embed)
                            print(f"Triggered event: {event['name']}")
                        else:
                            print(f"Error: Could not find channel {self.channel_id} to post event {event['name']}")
                        
                        events_to_remove.append(event)
                except ValueError:
                    print(f"Error parsing date for event: {event}")
                    events_to_remove.append(event) # Remove malformed events

            if events_to_remove:
                for e in events_to_remove:
                    if e in self.events:
                        self.events.remove(e)
                self.save_events()

            await asyncio.sleep(60) # Check every 60 seconds

    async def on_message(self, message):
        if message.author == self.user:
            return

        # Simple Command Parsing
        if message.content.startswith('!add_event'):
            # Format: !add_event "Name" "YYYY-MM-DD" "HH:MM" "Description" [ImageURL]
            try:
                import shlex
                parts = shlex.split(message.content)
                # parts[0] is !add_event
                
                # Check for at least Name, Date, Time, Description (5 parts total including command)
                if len(parts) < 5:
                    await message.reply('Usage: `!add_event "Name" "YYYY-MM-DD" "HH:MM" "Description" [ImageURL]` (or attach an image)')
                    return
                
                name = parts[1]
                date_str = parts[2]
                time_str = parts[3]
                description = parts[4]
                
                # Combine Date and Time
                full_time_str = f"{date_str} {time_str}"
                
                image_url = None
                if message.attachments:
                    image_url = message.attachments[0].url
                elif len(parts) > 5:
                    image_url = parts[5]

                # Validate Time
                try:
                    datetime.strptime(full_time_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    await message.reply('Error: Invalid Date/Time Format. Use "YYYY-MM-DD" "HH:MM" (24-hour). Example: "2024-12-25" "14:30"')
                    return

                new_event = {
                    "name": name,
                    "time": full_time_str,
                    "description": description,
                    "image_url": image_url,
                    "created_by": message.author.id
                }
                self.events.append(new_event)
                self.save_events()
                await message.reply(f"Event **{name}** added for `{full_time_str}`.")
                print(f"Event added: {name}")

            except Exception as e:
                await message.reply(f"Error adding event: {e}")

        elif message.content.startswith('!list_events'):
            if not self.events:
                await message.reply("No upcoming events scheduled.")
                return

            embed = discord.Embed(title="Upcoming Events", color=0x3498DB)
            for i, event in enumerate(self.events):
                embed.add_field(
                    name=f"{i+1}. {event['name']} ({event['time']})",
                    value=event['description'],
                    inline=False
                )
            await message.reply(embed=embed)

        elif message.content.startswith('!delete_event'):
            try:
                parts = message.content.split()
                if len(parts) < 2:
                    await message.reply("Usage: `!delete_event <number>`")
                    return
                
                index = int(parts[1]) - 1
                if 0 <= index < len(self.events):
                    removed = self.events.pop(index)
                    self.save_events()
                    await message.reply(f"Deleted event: **{removed['name']}**")
                else:
                    await message.reply("Invalid event number.")
            except ValueError:
                await message.reply("Please provide a valid number.")
