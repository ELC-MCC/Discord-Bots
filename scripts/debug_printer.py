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
    
    base_url_env = os.getenv(url_env)
    
    if not base_url_env:
        print(f"[{index}] No {url_env} found in environment (.env).")
        return

    # Extract Host from URL
    # e.g. http://192.168.1.121:7125 -> 192.168.1.121
    host = "unknown"
    try:
        if "://" in base_url_env:
            host = base_url_env.split("://")[1].split("/")[0].split(":")[0]
        else:
            host = base_url_env.split(":")[0]
    except:
        pass

    # Ports to try: Env var port first, then defaults
    ports_to_try = []
    
    # 1. Port from ENV
    try:
        from_env = base_url_env.split("://")[1].split("/")[0]
        if ":" in from_env:
            ports_to_try.append(from_env.split(":")[1])
    except:
        pass

    # 2. Common Defaults
    ports_to_try.extend(["7125", "80", "8080", "443"])
    
    # Remove duplicates preserving order
    unique_ports = []
    [unique_ports.append(p) for p in ports_to_try if p not in unique_ports]

    print(f"[{index}] Checking Host: {host} on ports: {unique_ports}")

    for port in unique_ports:
        scheme = "https" if port == "443" else "http"
        base_url = f"{scheme}://{host}:{port}"
        api_url = f"{base_url}/printer/objects/query?print_stats&display_status"
        
        try:
            print(f"[{index}]   Trying {base_url} ...", end="", flush=True)
            with urllib.request.urlopen(api_url, timeout=2) as response:
                code = response.getcode()
                if code == 200:
                    print(" SUCCESS!")
                    body = response.read().decode('utf-8')
                    data = json.loads(body)
                    
                    status = data.get('result', {}).get('status', {})
                    print_stats = status.get('print_stats', {})
                    
                    state = print_stats.get('state', 'Unknown')
                    filename = print_stats.get('filename', 'None')
                    progress = status.get('display_status', {}).get('progress', 0)
                    
                    print(f"[{index}]     State: {state} | Progress: {progress*100:.1f}% | File: {filename}")
                    print(f"[{index}]     *** FOUND CORRECT URL: {base_url} ***")
                    return # Stop after finding working port
                else:
                    print(f" Failed (Status {code})")
                    
        except urllib.error.URLError as e:
            print(f" Failed ({e.reason})")
        except Exception as e:
             print(f" Error ({e})")
    
    print(f"[{index}] ALL ATTEMPTS FAILED for {host}")

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
