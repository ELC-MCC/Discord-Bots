import os
import sys
import json
import urllib.request
import urllib.error
import time

# Basic .env parser if dotenv is not installed
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
    else:
        print("WARNING: .env file not found in current or parent directory.")

    # Update environment
    for k, v in env_vars.items():
        if k not in os.environ:
            os.environ[k] = v

load_env_file()

def check_printer(index):
    url_env = f"PRINTER_{index}_URL"
    base_url = os.getenv(url_env)
    
    if not base_url:
        print(f"[{index}] No {url_env} found in environment (.env).")
        return

    print(f"[{index}] Checking {base_url}...")
    
    # Klipper/Moonraker API
    api_url = f"{base_url}/printer/objects/query?print_stats&display_status"
    
    try:
        # 5 second timeout
        with urllib.request.urlopen(api_url, timeout=5) as response:
            code = response.getcode()
            
            if code == 200:
                body = response.read().decode('utf-8')
                data = json.loads(body)
                
                status = data.get('result', {}).get('status', {})
                print_stats = status.get('print_stats', {})
                
                state = print_stats.get('state', 'Unknown')
                filename = print_stats.get('filename', 'None')
                progress = status.get('display_status', {}).get('progress', 0)
                
                print(f"[{index}] Connection SUCCESS")
                print(f"[{index}] State: {state}")
                print(f"[{index}] Progress: {progress*100:.1f}%")
                print(f"[{index}] Filename: {filename}")
            else:
                print(f"[{index}] Connection ERROR: Status {code}")
                
    except urllib.error.URLError as e:
        print(f"[{index}] FAILED to connect: {e}")
    except Exception as e:
        print(f"[{index}] ERROR: {e}")

def main():
    print("--- Printer API Debug Tool (No Dependencies) ---")
    print(f"Python Version: {sys.version.split()[0]}")
    print(f"CWD: {os.getcwd()}")
    
    # Check if .env was loaded successfully by checking a known var or PRINTER_1_URL
    if not os.getenv('PRINTER_1_URL') and not os.getenv('STREAM_1_URL'):
         print("WARNING: Could not find PRINTER_1_URL or STREAM_1_URL in environment.")
         print("Make sure you are running this from the root directory where .env is located.")
    
    for i in range(1, 4):
        check_printer(i)
    print("--- Done ---")

if __name__ == "__main__":
    main()
