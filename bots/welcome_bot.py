import discord
import time
import random
import os

class WelcomeBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_welcome_time = {}  # Track last welcome time for each member ID

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        # Set nickname in all servers
        for guild in self.guilds:
            try:
                await guild.me.edit(nick="Jeff the Doorman")
                print(f"Changed nickname to 'Jeff the Doorman' in {guild.name}")
            except discord.Forbidden:
                print(f"Missing permissions to change nickname in {guild.name}")
            except Exception as e:
                print(f"Failed to change nickname in {guild.name}: {e}")

    async def on_member_join(self, member):
        """
        Event triggered when a new member joins the server.
        Sends a welcome message to a specific channel.
        """
        # Debounce check: Ignore if welcomed in the last 10 seconds
        current_time = time.time()
        if member.id in self.last_welcome_time and (current_time - self.last_welcome_time[member.id] < 10):
            print(f"Ignored duplicate on_member_join event for {member.name} (ID: {member.id})")
            return
        
        self.last_welcome_time[member.id] = current_time
        
        print(f"Member joined: {member.name} (ID: {member.id})")
        
        guild = member.guild

        # Try to find the specific channel by ID
        target_channel_id = int(os.getenv('WELCOME_CHANNEL_ID', '0'))
        channel = guild.get_channel(target_channel_id)

        # Fallback to name search if ID not found (e.g., bot in a different server)
        if not channel:
            print(f"Channel ID {target_channel_id} not found. Searching by name...")
            target_channels = ["new-people", "welcome", "general"]
            for name in target_channels:
                found = discord.utils.get(guild.text_channels, name=name)
                if found:
                    channel = found
                    break
        
        if channel:
            # List of Engineering Puns
            puns = [
                # Electrical
                "Welcome! We hope you have the *potential* to be great here!",
                "Ohm my god, a new member!",
                "We're *currently* very excited to meet you!",
                "You act like a sine wave, you're always around!",
                "Don't be *resistant* to saying hello!",
                "We've been *waiting* for you with high frequency!",
                "Watt is up? Welcome to the team!",
                # Mechanical
                "We are *geared* up to meet you!",
                "It is *riveting* to have you here!",
                "We hope you *weld* well with the team!",
                "Let's *torque* about your projects!",
                "You make our team run like a well-oiled machine!",
                "We're under a lot of *pressure* to make a good impression!"
            ]
            
            title = random.choice(puns)
            
            # Random vibrant color
            colors = [0x00FFFF, 0xFF00FF, 0x00FF00, 0xFFA500, 0xFFFF00, 0x0000FF]
            color = random.choice(colors)

            embed = discord.Embed(
                title=title,
                description=f"Welcome to the ELC, {member.mention}! We are excited to have you here. Please check out the rules and introduce yourself!",
                color=color
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            
            # Fetch channel IDs from env
            general_id = os.getenv('GENERAL_CHANNEL_ID')
            intro_id = os.getenv('INTRODUCTIONS_CHANNEL_ID')
            maker_id = os.getenv('MAKER_GENERAL_CHANNEL_ID')

            # Add "Where to Start" field
            embed.add_field(
                name="🚀 Where to Start",
                value=(
                    f"• <#{general_id}> - General Chat\n"
                    f"• <#{intro_id}> - Introductions\n"
                    f"• <#{maker_id}> - Maker General"
                ),
                inline=False
            )
            
            # No footer as requested
            
            try:
                await channel.send(embed=embed)
                print(f"Sent welcome message for {member.name} in #{channel.name}")
            except discord.Forbidden:
                print(f"Error: Missing permissions to send messages in #{channel.name}")
            except Exception as e:
                print(f"Error sending welcome message: {e}")
        else:
            print(f"Could not find any of the following channels: {', '.join(target_channels)} to greet {member.name}")
