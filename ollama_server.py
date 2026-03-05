import os
import re
import requests
import signal
import socket
import time
import logging

# --- CONFIGURATION ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONFIG = {
    "HOST_IP": "172.21.0.1",
    "MASTER_IP": "127.0.0.1",
    "MASTER_PORT": 8888,
    "USER": "test",
    "PASS": "test",
    "MODEL": "llama3.1:8b",
}

URL_OLLAMA = f"http://{CONFIG['HOST_IP']}:11434/api/chat"

PROMPTS = {
    "simple": (
        "ROLE: Jukebox Switch. MAPPING: 1:Pause/Play, 2:Previous, 3:Next, "
        "4:Volume Down, 5:Volume Up, 6:Shuffle, 7:Info, 8: playlist name. "
        "RULE: Return ONLY the INTEGER code. If ambiguous, return 0."
    ),
    "playlist": (
        "TASK: Extract ONLY the playlist name. FORMAT: Return only the string. "
        "RULES: No sentences, no markdown, no punctuation. If not a playlist, return '0'."
    ),
    "others": "General Assistant. Respond very briefly."
}

class MasterClient:
    """Gère la communication persistante avec le serveur Master."""
    def __init__(self, host, port, user, password):
        self.address = (host, port)
        self.auth_creds = f"{user};{password}"
        self.sock = None

    def connect(self):
        try:
            self.close() # On ferme l'ancien socket si il existe
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(3.0)
            self.sock.connect(self.address)
            self.sock.send(self.auth_creds.encode())
            
            resp = self.sock.recv(1024).decode()
            if "Connected" in resp:
                logging.info("Successfully connected to Master")
                return True
        except Exception as e:
            logging.error(f"Connection to Master failed: {e}")
        return False

    def send_command(self, cmd):
        if not self.sock:
            if not self.connect(): return
            
        try:
            payload = f"{CONFIG['USER']};{cmd}"
            self.sock.send(payload.encode())
            logging.info(f"Sent to Master: {payload}")
        except (socket.error, BrokenPipeError):
            logging.warning("Master connection lost. Retrying...")
            if self.connect():
                self.send_command(cmd)

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None

class Processor:
    """Logique de traitement de texte et appels LLM."""
    VLC_VARIANTS = ["vlc", "dlc", "wrc", "vsc", "gsc", "plc", "dsc", "vhc", "tlc", "jlc", "vls", "blc", "clc", "pln", "l.c", "vst"]
    PLAY_VARIANTS = ["playlist", "plélisto", "play historo", "playhistor"]

    @staticmethod
    def clean_text(data, wake_word="command"):
        text = data.lower().replace(",", "").replace(".", "").replace(wake_word, "", 1).strip()
        
        is_vlc = any(v in text for v in Processor.VLC_VARIANTS)
        for v in Processor.VLC_VARIANTS: text = text.replace(v, "").strip()
            
        is_playlist = any(v in text for v in Processor.PLAY_VARIANTS)
        for v in Processor.PLAY_VARIANTS: text = text.replace(v, "").strip()
            
        return text, is_vlc, is_playlist

    @staticmethod
    def call_ollama(text, system_prompt):
        payload = {
            "model": CONFIG["MODEL"],
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 10, "top_k": 1}
        }
        try:
            start = time.time()
            r = requests.post(URL_OLLAMA, json=payload, timeout=15)
            content = r.json().get("message", {}).get("content", "").strip().replace('"', '')
            logging.info(f"Ollama response ({round(time.time()-start, 2)}s): {content}")
            return content
        except Exception as e:
            logging.error(f"Ollama API Error: {e}")
            return "0"

def start_server():
    master = MasterClient(CONFIG["MASTER_IP"], CONFIG["MASTER_PORT"], CONFIG["USER"], CONFIG["PASS"])
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("0.0.0.0", 5000))
        server_sock.listen(5)
        logging.info("AI Server listening on port 5000")

        while True:
            client, addr = server_sock.accept()
            with client:
                try:
                    data = client.recv(1024).decode('utf-8').strip()
                    if not data or "command" not in data.lower():
                        continue

                    clean_text, is_vlc, is_playlist = Processor.clean_text(data)
                    
                    # Détermination du mode
                    if is_playlist:
                        # res = Processor.call_ollama(clean_text, PROMPTS["playlist"])
                        # Validation spécifique playlist
                        pattern = r'\b(touhou|rock)\b'
                        match = re.search(pattern, clean_text.lower())
                        final_cmd = f"playlist playlist {match.group(1)}" if match else None
                    elif is_vlc:
                        res = Processor.call_ollama(clean_text, PROMPTS["simple"])
                        final_cmd = f"VLC {res}" if res != "0" else None
                    else:
                        final_cmd = Processor.call_ollama(clean_text, PROMPTS["others"])

                    if final_cmd:
                        print("SENT:", final_cmd)
                        master.send_command(final_cmd)

                except Exception as e:
                    logging.error(f"Processing error: {e}")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: os._exit(0))
    start_server()