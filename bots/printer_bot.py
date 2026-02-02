import discord
import asyncio
import aiohttp
import os
import json
from datetime import datetime

class PrinterBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.printer_ips = []
        self.printer_states = {}  # Map IP -> Last Known State
        self.log_channel_id = None
        self.bg_task = None
        self.config_file = 'printer_config.json'

    async def start(self, token, **kwargs):
        # Load Env Vars
        raw_ips = os.getenv('PRINTER_IPS', '')
        self.printer_ips = [ip.strip() for ip in raw_ips.split(',') if ip.strip()]
        
        # Load Config (Persistent)
        self.load_config()
        
        # Fallback to Env if not in config
        if not self.log_channel_id:
            try:
                self.log_channel_id = int(os.getenv('PRINT_LOG_CHANNEL_ID', '0'))
            except ValueError:
                pass

        return await super().start(token, **kwargs)
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.log_channel_id = data.get('log_channel_id')
                    print(f"Loaded config: log_channel_id={self.log_channel_id}")
            except Exception as e:
                print(f"Error loading config: {e}")

    def save_config(self):
        data = {'log_channel_id': self.log_channel_id}
        try:
            with open(self.config_file, 'w') as f:
                json.dump(data, f)
            print("Config saved.")
        except Exception as e:
            print(f"Error saving config: {e}")

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f"Monitoring Printers: {self.printer_ips}")
        
        for guild in self.guilds:
            try:
                await guild.me.edit(nick="3D Print Observer")
            except Exception:
                pass

        if not self.bg_task:
            self.bg_task = self.loop.create_task(self.monitor_printers())

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.content.startswith('!set_printer_channel'):
            if not message.author.guild_permissions.administrator:
                await message.reply("❌ Admin permission required.")
                return
            
            self.log_channel_id = message.channel.id
            self.save_config()
            await message.reply(f"✅ Printer notifications will now appear in {message.channel.mention}")

    async def monitor_printers(self):
        await self.wait_until_ready()
        
        while not self.is_closed():
            for ip in self.printer_ips:
                await self.check_printer(ip)
            
            await asyncio.sleep(5)  # Check every 5 seconds

    async def check_printer(self, ip):
        # Try standard HTTP port 80 (Elegoo often proxies Moonraker here)
        # Endpoint: /printer/objects/query
        url = f"http://{ip}/printer/objects/query?print_stats&virtual_sdcard"
        
        try:
            print(f"DEBUG: Checking {ip} on port 80...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=3) as response:
                    print(f"DEBUG: {ip} responded with {response.status}")
                    if response.status != 200:
                        return
                    
                    data = await response.json()
                    result = data.get('result', {}).get('status', {})
                    
                    print_stats = result.get('print_stats', {})
                    
                    current_state = print_stats.get('state', 'unknown')
                    filename = print_stats.get('filename', 'Unknown')
                    
                    print(f"DEBUG: {ip} State: {current_state}, File: {filename}")

                    # Get last state
                    last_state = self.printer_states.get(ip, {}).get('state', 'unknown')
                    
                    # Detect Changes
                    if current_state != last_state:
                         print(f"DEBUG: State changed from {last_state} to {current_state}")
                         await self.handle_state_change(ip, last_state, current_state, print_stats)
                    
                    # Update State
                    self.printer_states[ip] = {
                        'state': current_state, 
                        'filename': filename
                    }

        except Exception as e:
            print(f"DEBUG: Failed to connect to {ip}: {e}")

    async def handle_state_change(self, ip, old_state, new_state, stats):
        if not self.log_channel_id:
            return

        channel = self.get_channel(self.log_channel_id)
        if not channel:
            return

        filename = stats.get('filename', 'Unknown')
        message = stats.get('message', '')

        # Filter out noisy transitions if needed. 
        # Common states: standby, printing, paused, complete, error
        
        embed = None
        
        if new_state == "printing" and old_state != "printing":
            embed = discord.Embed(title="🖨️ Print Started", color=0xF1C40F)
            embed.add_field(name="File", value=filename, inline=False)
            embed.add_field(name="Printer IP", value=ip, inline=True)
            
        elif new_state == "complete":
             print_time = stats.get('print_duration', 0)
             duration_str = f"{print_time/60:.2f} mins"
             
             embed = discord.Embed(title="✅ Print Finished", color=0x2ECC71)
             embed.add_field(name="File", value=filename, inline=False)
             embed.add_field(name="Duration", value=duration_str, inline=True)
             embed.add_field(name="Printer IP", value=ip, inline=True)

        elif new_state == "error":
             embed = discord.Embed(title="❌ Print Failed", color=0xE74C3C)
             embed.add_field(name="File", value=filename, inline=False)
             embed.add_field(name="Error", value=message, inline=False)
             embed.add_field(name="Printer IP", value=ip, inline=True)

        if embed:
            embed.set_footer(text=f"3D Print Observer • {datetime.now().strftime('%H:%M:%S')}")
            await channel.send(embed=embed)
