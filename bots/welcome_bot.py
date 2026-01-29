import discord

class WelcomeBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
        guild = member.guild
        
        # Try to find a channel named 'new-people'
        channel = discord.utils.get(guild.text_channels, name="new-people")
        
        if channel:
            embed = discord.Embed(
                title=f"Welcome to the ELC, {member.name}!",
                description=f"We are excited to have you here, {member.mention}. Please check out the rules and introduce yourself!",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"Member #{guild.member_count}")
            
            await channel.send(embed=embed)
            print(f"Sent welcome message for {member.name} in {channel.name}")
        else:
            print(f"Could not find a 'welcome' or 'general' channel to greet {member.name}")
