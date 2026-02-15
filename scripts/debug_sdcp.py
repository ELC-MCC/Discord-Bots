import socket
import struct
import os
import sys
import base64
import hashlib
import time
import json
import urllib.parse

# --- Minimal WebSocket Implementation ---

def create_ws_key():
    key = os.urandom(16)
    return base64.b64encode(key).decode('utf-8')

def ws_handshake(sock, host, port, path="/websocket"):
    key = create_ws_key()
    headers = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
        "\r\n"
    ]
    request = "\r\n".join(headers).encode('utf-8')
    sock.sendall(request)
    
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("Server closed connection during handshake")
        response += chunk
    
    if b"101 Switching Protocols" not in response:
        print(f"Handshake Response: {response.decode('utf-8', errors='ignore')}")
        raise ConnectionError("Handshake failed")
    return True

def ws_send_text(sock, text):
    data = text.encode('utf-8')
    length = len(data)
    
    # Frame format: FIN=1, RSV=0, Opcode=1 (text) -> 0x81
    header = bytearray([0x81])
    
    # Mask bit = 1
    if length <= 125:
        header.append(length | 0x80)
    elif length <= 65535:
        header.append(126 | 0x80)
        header.extend(struct.pack("!H", length))
    else:
        header.append(127 | 0x80)
        header.extend(struct.pack("!Q", length))
        
    mask_key = os.urandom(4)
    header.extend(mask_key)
    
    masked_data = bytearray(length)
    for i in range(length):
        masked_data[i] = data[i] ^ mask_key[i % 4]
        
    sock.sendall(header + masked_data)

def ws_recv_frame(sock):
    header = sock.recv(2)
    if not header: return None
    
    b1, b2 = header
    fin = b1 & 0x80
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    payload_len = b2 & 0x7F
    
    if payload_len == 126:
        payload_len = struct.unpack("!H", sock.recv(2))[0]
    elif payload_len == 127:
        payload_len = struct.unpack("!Q", sock.recv(8))[0]
        
    if masked:
        mask_key = sock.recv(4)
        
    data = b""
    while len(data) < payload_len:
        chunk = sock.recv(payload_len - len(data))
        if not chunk: break
        data += chunk
        
    if masked:
        unmasked = bytearray(len(data))
        for i in range(len(data)):
            unmasked[i] = data[i] ^ mask_key[i % 4]
        data = unmasked
        
    return opcode, data

# --- Main Script ---

def load_env_file():
    # Look for .env in current and parent dir
    locations = ['.env', '../.env']
    for loc in locations:
        if os.path.exists(loc):
            try:
                with open(loc, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'): continue
                        if '=' in line:
                            k, v = line.split('=', 1)
                            os.environ[k.strip()] = v.strip().strip("'").strip('"')
                print(f"Loaded {loc}")
                return
            except: pass
    print("Warning: .env not found")

def check_sdcp(index):
    url_env = f"PRINTER_{index}_URL"
    base_url = os.getenv(url_env)
    
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
        
    port = 3030
    print(f"[{index}] Sending WebSocket handshake to {host}:{port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        
        ws_handshake(sock, host, port)
        print(f"[{index}] Handshake Success! Sending status request...")
        
        # SDCP Get Status Command
        # This is a guess based on common SDCP structures.
        timestamp = int(time.time() * 1000)
        status_cmd = {
            "Id": f"{timestamp}",
            "Data": {
                "Cmd": 0, # 0 often means "Info" or "Status" in some versions, or maybe "GetStatus" string
                "Data": {}
            },
            "Topic": "sdcp/request/status"
        }
        
        # Try a few variations if we aren't sure
        cmds_to_try = [
            # 1. Standard GetStatus
            json.dumps({
                "Id": f"{int(time.time()*1000)}", 
                "Topic": "sdcp/request/status",
                "Data": {"Cmd": "GetStatus"} 
            }),
            # 2. GetAttributes (often used for initial state)
            json.dumps({
                "Id": f"{int(time.time()*1000)+1}",
                "Topic": "sdcp/request/attributes",
                "Data": {"Cmd": "GetAttributes"}
            }),
             # 3. Simple Cmd: 0
             json.dumps({
                "Id": f"{int(time.time()*1000)+2}", 
                "Topic": "sdcp/request/status",
                "Data": {"Cmd": 0} 
            }),
            # 4. Empty Data
            json.dumps({
                "Id": f"{int(time.time()*1000)+3}",
                "Topic": "sdcp/request/status",
                "Data": {}
            })
        ]

        print(f"[{index}] Sending {len(cmds_to_try)} command variations...")
        for cmd in cmds_to_try:
            print(f"[{index}] >> {cmd}")
            ws_send_text(sock, cmd)
            time.sleep(1.0) # Wait a bit between commands
        
        # Listen for a few seconds
        print(f"[{index}] Listening for 10 seconds...")
        start_time = time.time()
        while time.time() - start_time < 10:
            try:
                opcode, data = ws_recv_frame(sock)
                if opcode == 0x8: # Close
                    print(f"[{index}] Server sent Close frame")
                    break
                if opcode == 0x1: # Text
                    text = data.decode('utf-8')
                    # Pretty print JSON if possible
                    try:
                        j = json.loads(text)
                        print(f"[{index}] RECV JSON: {json.dumps(j, indent=2)}")
                        
                        # Check for Status
                        if 'Data' in j and 'Status' in j['Data']:
                             pass # Found it!
                    except:
                        print(f"[{index}] RECV Text: {text}")
            except socket.timeout:
                pass
            except Exception as e:
                print(f"[{index}] Read Error: {e}")
                break
                
        # Try sending a status request if quiet?
        # status_cmd = {"Id": "1", "Data": {"Cmd": "GetStatus"}, "Topic": "sdcp/request/status"}
        # ws_send_text(sock, json.dumps(status_cmd))
        
        sock.close()
    except Exception as e:
        print(f"[{index}] Failed: {e}")

if __name__ == "__main__":
    load_env_file()
    print("--- SDCP Debug Tool (Zero Dependency) ---")
    for i in range(1, 4):
        check_sdcp(i)
