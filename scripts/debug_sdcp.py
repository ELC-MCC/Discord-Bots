import socket
import struct
import os
import sys
import base64
import hashlib
import time
import json
import urllib.request
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

def check_udp_discovery(index, specific_host=None):
    # SDCP Discovery: Send "M99999" to port 3000
    target_desc = f"host {specific_host}" if specific_host else "BROADCAST"
    print(f"[{index}] Sending UDP 'M99999' to {target_desc} on port 3000...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if not specific_host:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        target_addr = ('<broadcast>', 3000)
    else:
        target_addr = (specific_host, 3000)
        
    sock.settimeout(2) # Shorter timeout for unicast checks
    
    found_id = None
    
    try:
        # Send Message
        message = b"M99999"
        sock.sendto(message, target_addr)
        
        start_time = time.time()
        while time.time() - start_time < 2:
            try:
                data, addr = sock.recvfrom(4096)
                text = data.decode('utf-8', errors='ignore')
                # If checking specific host, ignore others? Nah, any info is good.
                
                if text.strip().startswith('{'):
                    try:
                        j = json.loads(text)
                        print(f"[{index}] UDP RAW JSON: {json.dumps(j, indent=2)}")
                        
                        # Check multiple locations for MainboardID
                        # It might be in Data.MainboardID or just MainboardID
                        mb_id = j.get('Data', {}).get('MainboardID') or j.get('MainboardID')
                        
                        if mb_id:
                            print(f"[{index}] *** FOUND MainboardID via UDP: {mb_id} ***")
                            found_id = mb_id
                            # return found_id # Don't return yet, we want to see the JSON!
                    except: pass
            except socket.timeout:
                pass
            except Exception as e:
                print(f"[{index}] UDP Recv Error: {e}")
                break
    except Exception as e:
        print(f"[{index}] UDP Send Error: {e}")
    finally:
        sock.close()
    return found_id

def check_http_id(index, host):
    # Try to find ID in javascript variables on the web page
    print(f"[{index}] Scraping HTTP {host} for MainboardID...")
    try:
        url = f"http://{host}/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            html = response.read().decode('utf-8', errors='ignore')
            # Look for common patterns
            # e.g. "MainboardID":"..."
            if 'MainboardID' in html:
                # Poor man's regex/parsing
                parts = html.split('MainboardID')
                if len(parts) > 1:
                    # Look at the part after
                    snippet = parts[1][:50]
                    # usually ":"ID" or similar
                    clean = snippet.replace('"', '').replace("'", '').replace(':', '').replace('=', '').strip()
                    # take first alphanumeric chunk
                    candidate = clean.split()[0].split(',')[0].split('}')[0]
                    print(f"[{index}] *** FOUND MainboardID via HTTP Scrape: {candidate} ***")
                    return candidate
    except Exception as e:
        print(f"[{index}] HTTP Scrape failed: {e}")
    return None

def check_sdcp(index, mainboard_id=None):
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
        
        topic_status = "sdcp/request/status"
        if mainboard_id:
            topic_status = f"sdcp/request/{mainboard_id}/status" # Guessing topic format
        
        # Commands to try based on V3.0.0 and Community findings
        cmds_to_try = []
        
        if mainboard_id:
            # Topic: sdcp/request/{MainboardID}
            topic = f"sdcp/request/{mainboard_id}"
            
            # 1. Login/Connect (Cmd 1 or 256?)
            # Some sources say no login needed for local, but maybe "Connect" needed?
            
            # Try 1: Cmd 1 (Status?)
            cmds_to_try.append(json.dumps({
                "Id": f"{int(time.time()*1000)}", 
                "Topic": topic,
                "Data": {"Cmd": 1, "MainboardID": mainboard_id, "From": "Client"} 
            }))

            # Try 2: Cmd 0 (Info?)
            cmds_to_try.append(json.dumps({
                 "Id": f"{int(time.time()*1000)+1}",
                 "Topic": topic,
                 "Data": {"Cmd": 0, "MainboardID": mainboard_id, "From": "Client"}
            }))

            # Try 3: Cmd 128 (GetStatus - observed in some logs)
            cmds_to_try.append(json.dumps({
                 "Id": f"{int(time.time()*1000)+2}",
                 "Topic": topic,
                 "Data": {"Cmd": 128, "MainboardID": mainboard_id, "From": "Client"}
            }))
             
             # Try 4: String "GetStatus"
            cmds_to_try.append(json.dumps({
                "Id": f"{int(time.time()*1000)+3}", 
                "Topic": topic,
                "Data": {"Cmd": "GetStatus", "MainboardID": mainboard_id, "From": "Client"} 
            }))
            
        else:
             cmds_to_try.append(json.dumps({
                "Id": f"{int(time.time()*1000)}", 
                "Topic": "sdcp/request/status",
                "Data": {"Cmd": "GetStatus"} 
            }))

        print(f"[{index}] Sending {len(cmds_to_try)} command variations to {host}...")
        for cmd in cmds_to_try:
            print(f"[{index}] >> {cmd}")
            ws_send_text(sock, cmd)
            time.sleep(1.0)
        
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
                        
                        # Check for Status
                        if 'Data' in j and 'Status' in j['Data']:
                             pass # Found it!
                        
                        print(f"[{index}] RECV JSON: {json.dumps(j, indent=2)}")
                    except:
                        print(f"[{index}] RECV Text: {text}")
            except socket.timeout:
                pass
            except Exception as e:
                print(f"[{index}] Read Error: {e}")
                break
                
        sock.close()
    except Exception as e:
        print(f"[{index}] Failed: {e}")

if __name__ == "__main__":
    load_env_file()
    print("--- SDCP Debug Tool (Zero Dependency) ---")
    
    for i in range(1, 4):
        url_env = f"PRINTER_{i}_URL"
        base_url = os.getenv(url_env)
        host = None
        if base_url:
            try:
                if "://" in base_url:
                    host = base_url.split("://")[1].split("/")[0].split(":")[0]
                else:
                    host = base_url.split(":")[0]
            except: pass
        
        mb_id = None
        
        # 1. Try Unicast UDP to this host
        if host:
            mb_id = check_udp_discovery(i, specific_host=host)
            
        # 2. Try Broadcast UDP if missed (only once ideally, but ok to repeat)
        if not mb_id:
             mb_id = check_udp_discovery(i, specific_host=None)
             
        # 3. Try HTTP Scrape
        if not mb_id and host:
            mb_id = check_http_id(i, host)
            
        if mb_id:
            print(f"[{i}] Using ID: {mb_id}")
        else:
            print(f"[{i}] No ID found. WebSocket might fail.")

        check_sdcp(i, mb_id)
