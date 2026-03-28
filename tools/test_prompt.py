import socket
import json
from config_loader import cfg
from tools.llm_agent import llm

def run_debug_server(host='0.0.0.0', port=28888):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)

    try:
        while True:
            client_sock, addr = server.accept()
            data = client_sock.recv(4096).decode('utf-8').strip()
            
            if data:
                # Expected format: signature:tag:content
                parts = data.split(':', 2)
                
                if len(parts) < 3:
                    client_sock.sendall(b"ERR_FORMAT\n")
                    client_sock.close()
                    continue

                sig, tag, content = parts

                if tag == "Auth":
                    client_sock.sendall(b"AUTH_OK\n")
                
                elif tag == "test":
                    agent_cfg_1 = cfg.sys.Global.router_agent
                    agent_cfg_2 = cfg.music_vlc.MUSIC_VLC.MUSIC_AGENT
                    
                    print(f"[*] Launching LLM inference (router_agent)...")
                    result = llm.execute(content, agent_cfg_1, verbose=True)
                    print(f"[RESULT JSON] : {result}")
                    
                    client_sock.sendall(f"PROCESSED:{result}\n".encode())
                    
    except AttributeError:
        print(f"[!] Error: Agent not found in YAML.")
        client_sock.sendall(b"ERR_CONFIG\n")
        client_sock.close()

    except KeyboardInterrupt:
        pass
    finally:
        server.close()

if __name__ == "__main__":
    run_debug_server()
