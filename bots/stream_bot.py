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
        self.has_started = False

    async def on_ready(self):
        logger.info(f"StreamBot logged in as {self.user}")
        
        if self.has_started:
            logger.info("StreamBot already started, skipping initialization.")
            return
        
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
        self.has_started = True

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
            # Add timeout for connection and read
            timeout = aiohttp.ClientTimeout(total=None, connect=10, sock_read=10)
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    logger.error(f"Failed to connect to stream {url}: {response.status}")
                    yield None
                    await asyncio.sleep(5)
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
                             
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Stream connection/read error {url}: {e}")
            yield None
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected stream error {url}: {e}")
            yield None
            await asyncio.sleep(5)

    async def stream_loop(self, channel, url, title, index):
        message = None
        last_status = "CONNECTING" 
        
        # Initial Embed
        embed = discord.Embed(title=title, color=0xF1C40F) # Yellow for connecting
        embed.set_footer(text=f"Status: CONNECTING • ID: {index}")
        
        # Try to find existing message
        try:
            async for history_msg in channel.history(limit=20):
                if history_msg.author == self.user and history_msg.embeds:
                    # Check footer to match Stream ID
                    footer_text = history_msg.embeds[0].footer.text
                    if footer_text and f"ID: {index}" in footer_text:
                        message = history_msg
                        # Update it to Connecting state
                        await message.edit(embed=embed)
                        break
                        
            if not message:
                 message = await channel.send(embed=embed)
        except Exception as e:
             logger.error(f"Failed to find/send initial message for {title}: {e}")

        # Mimic a browser to ensure the stream server wakes up
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            backoff = 1
            last_update = 0
            
            while not self.is_closed():
                try:
                    async for jpg_data in self.get_frame(session, url):
                        now = asyncio.get_running_loop().time()
                        
                        # Determine current status and color
                        if jpg_data is None:
                            current_status = "OFFLINE"
                            color = 0xE74C3C # Red
                        else:
                            current_status = "LIVE"
                            color = 0x2ECC71 # Green

                        # Force update if status changed or time interval passed
                        if (now - last_update >= self.update_interval) or (current_status != last_status):
                            
                            embed.color = color
                            embed.set_footer(text=f"Status: {current_status} • ID: {index}")
                            
                            try:
                                if not message:
                                    message = await channel.send(embed=embed)

                                if jpg_data:
                                    file = discord.File(BytesIO(jpg_data), filename="stream.jpg")
                                    embed.set_image(url="attachment://stream.jpg")
                                    await message.edit(embed=embed, attachments=[file])
                                else:
                                    # Offline - No image
                                    embed.set_image(url=None)
                                    await message.edit(embed=embed, attachments=[])
                                
                                last_status = current_status
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
            await message.channel.send("Restarting streams & purging channel...", delete_after=5)
            await self.purge_and_restart()

    async def purge_and_restart(self):
        # Cancel all streams first
        for task in self.stream_tasks:
            task.cancel()
        self.stream_tasks = []

        channel = self.get_channel(self.channel_id)
        if channel:
            try:
                # Purge channel
                await channel.purge(limit=100)
            except Exception as e:
                logger.error(f"Failed to purge channel: {e}")
        
        # Restart
        await self.start_streams()
