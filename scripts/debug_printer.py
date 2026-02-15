import asyncio
import aiohttp
import os
import sys

# Load .env manually if python-dotenv is not installed/working
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed, ensuring env vars are set manually")

async def check_printer(index):
    url_env = f"PRINTER_{index}_URL"
    base_url = os.getenv(url_env)
    
    if not base_url:
        print(f"[{index}] No {url_env} found in local environment (check .env).")
        return

    print(f"[{index}] Checking {base_url}...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try simple status query first
            api_url = f"{base_url}/printer/objects/query?print_stats&display_status"
            async with session.get(api_url, timeout=5) as response:
                print(f"[{index}] Status Code: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    status = data.get('result', {}).get('status', {})
                    print_stats = status.get('print_stats', {})
                    state = print_stats.get('state', 'Unknown')
                    filename = print_stats.get('filename', 'None')
                    print(f"[{index}] Connection SUCCESS")
                    print(f"[{index}] State: {state}")
                    print(f"[{index}] Filename: {filename}")
                else:
                    print(f"[{index}] Connection ERROR: {await response.text()}")
    except Exception as e:
        print(f"[{index}] FAILED to connect: {e}")

async def main():
    print("--- Printer API Debug Tool ---")
    print("Ensure you have set PRINTER_x_URL in your .env file.")
    
    tasks = [check_printer(i) for i in range(1, 4)]
    await asyncio.gather(*tasks)
    print("--- Done ---")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
