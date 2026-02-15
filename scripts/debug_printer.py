import os
import sys
import json
import urllib.request
import urllib.error
import time
import socket

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
    # 7125: Moonraker default
    # 80: Web Interface / HTTP API
    # 8080: Alternate HTTP
    # 443: HTTPS
    # 3030: Elegoo WebSocket (SDCP) check
    ports_to_try.extend(["7125", "80", "8080", "443", "3030"])
    
    # Remove duplicates preserving order
    unique_ports = []
    [unique_ports.append(p) for p in ports_to_try if p not in unique_ports]

    print(f"[{index}] Checking Host: {host}")

    # Paths to probe on Port 80
    paths_to_probe = [
        "/printer/objects/query?print_stats&display_status", # Standard Moonraker
        "/api/printer", # Mainsail/Fluidd sometimes
        "/moonraker/printer/objects/query?print_stats&display_status", # Reverse Proxy
        "/", # Root (Check title)
        "/api/version"
    ]

    print(f"[{index}] Checking Host: {host}")

    # Paths to probe on Port 80
    paths_to_probe = [
        "/printer/objects/query?print_stats&display_status",
        "/api/printer",
        "/moonraker/printer/objects/query?print_stats&display_status",
        "/", 
        "/api/version"
    ]
    
    # Check Ports (TCP)
    open_ports = []
    for port in unique_ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            result = sock.connect_ex((host, int(port)))
            if result == 0:
                print(f"[{index}]   Port {port} is OPEN")
                open_ports.append(port)
            else:
                print(f"[{index}]   Port {port} is CLOSED")
            sock.close()
        except Exception:
            print(f"[{index}]   Port {port} check error")

    # Probe HTTP on Open Ports
    for port in open_ports:
        scheme = "https" if port == "443" else "http"
        base_url = f"{scheme}://{host}:{port}"
        
        # If port 80, try specific paths
        current_paths = paths_to_probe if port == "80" else ["/printer/objects/query?print_stats&display_status", "/"]

        for path in current_paths:
            url = f"{base_url}{path}"
            # ... (rest of HTTP probing logic)
            try:
                print(f"[{index}]   Probing {url} ...", end="", flush=True)
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'Mozilla/5.0')
                
                with urllib.request.urlopen(req, timeout=2) as response:
                    code = response.getcode()
                    content_type = response.headers.get('Content-Type', '')
                    print(f" Status {code} ({content_type})")
                    
                    body = response.read().decode('utf-8', errors='ignore')
                    
                    if code == 200:
                        if 'json' in content_type:
                            try:
                                data = json.loads(body)
                                if 'result' in data and 'status' in data['result']:
                                    print(f"[{index}]     *** FOUND COMPATIBLE API at {url} ***")
                                    return
                            except: pass
                        elif '<title>' in body:
                            start = body.find('<title>') + 7
                            end = body.find('</title>')
                            print(f"[{index}]     Page Title: {body[start:end].strip()}")

            except urllib.error.HTTPError as e:
                print(f" Failed ({e.code})")
            except Exception as e:
                print(f" Failed (Error)")

    print(f"[{index}] Could not find Moonraker API.")

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
