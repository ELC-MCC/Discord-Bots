import discord
import asyncio
import aiohttp
import os
import logging
from io import BytesIO
import bot_config

# Setup Logging
logger = logging.getLogger("StreamBot")

class StreamBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_tasks = []
        self.channel_id = None
        self.update_interval = 3.0 # Seconds

    async def on_ready(self):
        logger.info(f"StreamBot logged in as {self.user}")
        
        try:
            self.channel_id = int(os.getenv('STREAM_CHANNEL_ID', '0'))
        except ValueError:
            self.channel_id = 0

        if self.channel_id == 0:
            logger.warning("STREAM_CHANNEL_ID not set or invalid.")
            return

        # Set Nickname
        for guild in self.guilds:
            try:
                await guild.me.edit(nick=bot_config.STREAM_BOT_NICKNAME)
            except Exception as e:
                logger.error(f"Failed to change nickname in {guild.name}: {e}")

        # Start streams
        await self.start_streams()

    async def start_streams(self):
        # Cancel existing tasks if any
        for task in self.stream_tasks:
            task.cancel()
        self.stream_tasks = []

        channel = self.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Stream Channel ID {self.channel_id} not found.")
            return

        # Look for streams 1 through 5 (arbitrary limit)
        for i in range(1, 6):
            url = os.getenv(f'STREAM_{i}_URL')
            title = os.getenv(f'STREAM_{i}_TITLE', f"Stream {i}")
            
            if url:
                print(f"Starting stream {i}: {title}")
                task = self.loop.create_task(self.stream_loop(channel, url, title, i))
                self.stream_tasks.append(task)

    async def get_frame(self, session, url):
        buffer = b""
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to connect to stream {url}: {response.status}")
                    return

                async for chunk in response.content.iter_chunked(4096):
                    buffer += chunk
                    
                    while True:
                        a = buffer.find(b'\xff\xd8')
                        b = buffer.find(b'\xff\xd9')
                        
                        if a != -1 and b != -1:
                            if a < b:
                                yield buffer[a:b+2]
                                buffer = buffer[b+2:]
                            else:
                                buffer = buffer[a:]
                        else:
                            break
                        
                    if len(buffer) > 5 * 1024 * 1024:
                         buffer = b""
                             
        except Exception as e:
            logger.error(f"Stream error {url}: {e}")
            await asyncio.sleep(5)

    async def stream_loop(self, channel, url, title, index):
        message = None
        async with aiohttp.ClientSession() as session:
            backoff = 1
            last_update = 0
            
            while not self.is_closed():
                try:
                    async for jpg_data in self.get_frame(session, url):
                        now = asyncio.get_running_loop().time()
                        
                        if message is None or (now - last_update >= self.update_interval):
                            file = discord.File(BytesIO(jpg_data), filename="stream.jpg")
                            
                            embed = discord.Embed(title=title, color=0xFF0000)
                            embed.set_image(url="attachment://stream.jpg")
                            embed.set_footer(text=f"Live Feed • ID: {index}")

                            try:
                                if message:
                                    await message.edit(embed=embed, attachments=[file])
                                else:
                                    # Check history to find our own previous message to resume?
                                    # For now, just send a new one.
                                    message = await channel.send(embed=embed, file=file)
                                
                                last_update = now
                                backoff = 1
                                
                            except discord.NotFound:
                                message = None
                                last_update = 0
                            except Exception as e:
                                logger.error(f"Discord update error for {title}: {e}")
                
                except Exception as e:
                    logger.error(f"Stream Loop Crash {title}: {e}")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30)

    async def on_message(self, message):
        # Simple command to force restart streams if needed
        if message.content == "!restart_streams" and message.author.guild_permissions.administrator:
            await message.channel.send("Restarting streams...")
            await self.start_streams()
