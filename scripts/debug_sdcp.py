import asyncio
import json
import os
import sys

try:
    import aiohttp
except ImportError:
    print("Error: 'aiohttp' module not found.")
    print("Please install requirements or run in the correct environment:")
    print("  pip install -r requirements.txt")
    print("  or")
    print("  pip install aiohttp")
    sys.exit(1)

# Load .env manually
def load_env_file():
    env_vars = {}
    env_paths = ['.env', '../.env', os.path.join(os.path.dirname(__file__), '../.env')]
    
    target_path = None
    for path in env_paths:
        if os.path.exists(path):
            target_path = path
            break
            
    if target_path:
        print(f"Loading .env from: {os.path.abspath(target_path)}")
        try:
            with open(target_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip().strip("'").strip('"')
        except Exception as e:
            print(f"Failed to read .env: {e}")
    # Update environment
    for k, v in env_vars.items():
        if k not in os.environ:
            os.environ[k] = v

load_env_file()

async def debug_sdcp(index):
    url_env = f"PRINTER_{index}_URL"
    base_url = os.getenv(url_env) # e.g. http://192.168.1.121:7125 (formatted potentially wrong for this specific test, but we need the IP)
    
    if not base_url:
        print(f"[{index}] No {url_env} found.")
        return

    # Extract Host
    host = "unknown"
    try:
        if "://" in base_url:
            host = base_url.split("://")[1].split("/")[0].split(":")[0]
        else:
            host = base_url.split(":")[0]
    except:
        pass

    ws_url = f"ws://{host}:3030/websocket"
    print(f"[{index}] Connecting to {ws_url}...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(ws_url) as ws:
                print(f"[{index}] Connected!")
                
                # Check if we get a welcome message or status push
                try:
                    msg = await ws.receive_str(timeout=5)
                    print(f"[{index}] Received: {msg}")
                except asyncio.TimeoutError:
                    print(f"[{index}] No initial message received (timeout).")
                
                # Try sending a status request if silence
                # Command ID for "Get Status" or similar is often needed.
                # Common SDCP/Moonraker-ish commands?
                # Let's try sending an empty JSON or a basic ID/Cmd structure if we know one.
                # But first, just listen.
                
                # Just listen for a bit more
                end_time = asyncio.get_running_loop().time() + 10
                while asyncio.get_running_loop().time() < end_time:
                    try:
                        msg = await ws.receive_str(timeout=2)
                        print(f"[{index}] Received: {msg}")
                    except asyncio.TimeoutError:
                        pass
                        
    except Exception as e:
        print(f"[{index}] Connection Failed: {e}")

async def main():
    print("--- SDCP Debug Tool ---")
    tasks = [debug_sdcp(i) for i in range(1, 4)]
    await asyncio.gather(*tasks)
    print("--- Done ---")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
