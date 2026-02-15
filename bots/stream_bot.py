import discord
import asyncio
import aiohttp
import os
import logging
from io import BytesIO
import bot_config
import sys

# Add parent directory to path to find utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.sdcp_client import SDCPClient

# Setup Logging
logger = logging.getLogger("StreamBot")

class StreamBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stream_tasks = []
        self.channel_id = None
        self.update_interval = 3.0 # Seconds
        self.has_started = False
        self.sdcp_clients = {} # Cache clients per URL/IP

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
                            
                            # Fetch Printer Stats
                            printer_url = os.getenv(f'PRINTER_{index}_URL')
                            if not printer_url and url:
                                # Try to guess from stream URL
                                try:
                                    from urllib.parse import urlparse
                                    parsed = urlparse(url)
                                    if parsed.netloc:
                                        # Default Moonraker port
                                        host = parsed.netloc.split(':')[0]
                                        printer_url = f"http://{host}:7125"
                                except:
                                    pass

                            print_stats = {}
                            if printer_url:
                                print_stats = await self.fetch_printer_status(session, printer_url)

                            embed.color = color
                            
                            # Update Footer to just ID and basic status
                            embed.set_footer(text=f"Camera: {current_status} • ID: {index}")

                            # Build Description with Print Details
                            # Use placeholders if data is missing or state is not printing
                            
                            p_state_raw = print_stats.get('state', 'Idle')
                            p_state = p_state_raw.title()
                            p_file = print_stats.get('filename', '--')
                            p_progress = print_stats.get('progress', 0) * 100
                            
                            # Calculate Time Left / Elapsed
                            p_elapsed = "--"
                            p_left = "--"
                            
                            # Show stats for any active state (Printing, Heating, Starting, etc)
                            # Exclude Idle, Paused (maybe?), Error
                            inactive_states = ['Idle', 'Standby', 'Error', 'Offline']
                            
                            # Check if state implies activity. 
                            # We use lower() for comparison but p_state is Title Cased for display
                            if p_state_raw.lower() not in [s.lower() for s in inactive_states] and p_state_raw.lower() != 'paused':
                                if print_stats.get('print_duration') is not None:
                                    import datetime
                                    p_elapsed = str(datetime.timedelta(seconds=int(print_stats['print_duration'])))
                                    
                                    # Estimate Time Left
                                    # Priority 1: Use Total Duration from SDCP/Moonraker if available
                                    if print_stats.get('total_duration', 0) > 0:
                                        left = print_stats['total_duration'] - print_stats['print_duration']
                                        if left < 0: left = 0
                                        p_left = str(datetime.timedelta(seconds=int(left)))
                                    # Priority 2: Estimate based on progress
                                    elif print_stats.get('progress', 0) > 0:
                                        total_time = print_stats['print_duration'] / print_stats['progress']
                                        left = total_time - print_stats['print_duration']
                                        p_left = str(datetime.timedelta(seconds=int(left)))

                            # Format Description
                            description = f"**Status:** {p_state}\n"
                            
                            # Add Temperatures if available
                            if 'temps' in print_stats:
                                temps = print_stats['temps']
                                # Bed: Curr / Target
                                t_str = []
                                if temps.get('bed'):
                                    b_curr, b_target = temps['bed']
                                    t_str.append(f"Bed: {float(b_curr):.1f}°C / {float(b_target):.1f}°C")
                                if temps.get('nozzle'):
                                    n_curr, n_target = temps['nozzle']
                                    t_str.append(f"Noz: {float(n_curr):.1f}°C / {float(n_target):.1f}°C")
                                if temps.get('chamber'):
                                    c_curr = temps['chamber']
                                    try:
                                        t_str.append(f"Chamber: {float(c_curr):.1f}°C")
                                    except (ValueError, TypeError):
                                        pass
                                
                                if t_str:
                                    description += f"**Temps:** {' | '.join(t_str)}\n"

                            description += f"**File:** {p_file}\n"
                            
                            # Only show progress/times if NOT Idle
                            if p_state_raw != "Idle":
                                description += (
                                    f"**Progress:** {p_progress:.1f}%\n"
                                    f"**Elapsed:** {p_elapsed}\n"
                                    f"**Time Left:** {p_left}"
                                )
                            else:
                                # Optional: You could show just an empty line or nothing
                                pass

                            embed.description = description
                            
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

    async def fetch_printer_status(self, session, base_url):
        # 1. Try Moonraker / Klipper API first (Standard)
        try:
            url = f"{base_url}/printer/objects/query?print_stats&display_status"
            async with session.get(url, timeout=2) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get('result', {}).get('status', {})
                    
                    stats = result.get('print_stats', {})
                    display = result.get('display_status', {})
                    
                    # Check if we have valid data
                    filename = stats.get('filename')
                    state = stats.get('state')
                    
                    # If we are printing but have no filename, or if response is empty, 
                    # we might want to try SDCP as a fallback for Elegoo printers.
                    if state == "printing" and not filename:
                        logger.warning(f"Moonraker returned 'printing' but no filename for {base_url}. Trying SDCP fallback.")
                    elif state:
                         return {
                            'filename': filename,
                            'print_duration': stats.get('print_duration'),
                            'state': state,
                            'progress': display.get('progress', 0)
                        }
        except Exception as e:
            # Moonraker failed, ignore for now and try SDCP
            logger.debug(f"Moonraker fetch failed for {base_url}: {e}")
            pass

        # 2. Try SDCP (Elegoo)
        try:
            # Extract Host
            host = "unknown"
            if "://" in base_url:
                host = base_url.split("://")[1].split("/")[0].split(":")[0]
            else:
                host = base_url.split(":")[0]
                
            # Use cached client or create new
            if host not in self.sdcp_clients:
                self.sdcp_clients[host] = SDCPClient(host)
            
            client = self.sdcp_clients[host]
            
            # Fetch
            sdcp_result = await client.fetch_status()
            if sdcp_result:
                 return sdcp_result
            else:
                logger.debug(f"SDCP fetch returned empty for {host}")
                 
        except Exception as e:
            logger.error(f"Failed to fetch printer status (SDCP) {base_url}: {e}")
            
        return {}

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
