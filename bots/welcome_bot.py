import discord
import time

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
        target_channel_id = 886081479736709131
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
            embed = discord.Embed(
                title=f"Welcome to the ELC, {member.name}!",
                description=f"We are excited to have you here, {member.mention}. Please check out the rules and introduce yourself!",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"Member #{guild.member_count}")
            
            try:
                await channel.send(embed=embed)
                print(f"Sent welcome message for {member.name} in #{channel.name}")
            except discord.Forbidden:
                print(f"Error: Missing permissions to send messages in #{channel.name}")
            except Exception as e:
                print(f"Error sending welcome message: {e}")
        else:
            print(f"Could not find any of the following channels: {', '.join(target_channels)} to greet {member.name}")
