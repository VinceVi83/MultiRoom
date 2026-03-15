import socket
import ssl
import queue
import threading
import os
import requests
import time
from faster_whisper import WhisperModel
from core.router_llm import RouterLLM
from core.web_scrapper import ScrapperService
from core.config_loader import cfg
from core.UserSession import UserSession

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

@dataclass
class TaskContext:
    user_input: str
    session: any
    audio_path: str = None
    timestamp: datetime = field(default_factory=datetime.now)
    category: str = "Nonsense"
    label: str = "Nonsense"
    result: str = "Nonsense"
    duration: int = 0
    location: str = "None"

class SessionManager:
    def __init__(self):
        self.host = cfg.HOST_IP
        self.port = int(cfg.PORT_HUB)
        self.allowed_sigs = cfg.LIST_ALLOWED_SIGS
        self.user_count = 0
        self.active_sessions = {}
        
        print("[*] Loading Whisper (distil-large-v3/CPU)...")
        self.whisper = WhisperModel(
            "medium", 
            device="cpu", 
            compute_type="int8",
            cpu_threads=12,
            num_workers=1
        )
        print("[*] Loading RouterLLM...")
        self.router = RouterLLM()
        self.active_sessions["system"] = UserSession("system", self.user_count)
        self.user_count += 1

        self.task_queue = queue.Queue()
        threading.Thread(target=self._worker_loop, daemon=True).start()
        threading.Thread(target=self._cleanup_inactive_sessions, daemon=True).start()

    def _cleanup_inactive_sessions(self):
        while True:
            time.sleep(300)
            now = time.time()
            to_delete = []
            
            for username, session in list(self.active_sessions.items()):
                if username == "system":
                    continue
                
                if not session.socks:
                    if now - session.last_seen > 7200: 
                        print(f"[*] Timeout 2h: killall services link to {username}")
                        session.stop_all_services()
                        to_delete.append(username)
            
            for username in to_delete:
                del self.active_sessions[username]
    def _worker_loop(self):
        while True:
            session, payload = self.task_queue.get()
            try:
                if payload.startswith("http"):
                    self._handle_stt_request(session, payload)
                else:
                    self._handle_direct_command(session, payload)
            except Exception as e:
                print(f"[!] Worker Error: {e}")
            finally:
                self.task_queue.task_done()
    
    def _handle_direct_command(self, session, text):
        """Utilise directement l'objet session pour router l'action"""
        print(text)
        if text:
            print(f"[*] Transcription [{session.username}]: {text}")
            context = TaskContext(user_input=text, session=session)
            self.router.command_queue.put(context)

    def _handle_stt_request(self, session, url):
        """Mise à jour pour utiliser l'objet UserSession"""
        temp_file = f"/tmp/temp_{session.index}_{threading.get_ident()}.wav"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(temp_file, "wb") as f:
                    f.write(response.content)
                
                segments, _ = self.whisper.transcribe(
                    temp_file, 
                    beam_size=3,
                    language="fr",
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    initial_prompt="Vincent, Commande, Playlist, Touhou, Japonais",
                    
                )
                text = " ".join([segment.text for segment in segments]).strip()
                
                if text:
                    print(f"[*] Transcription [{session.username}]: {text}")
                    context = TaskContext(user_input=text, session=session, audio_path=temp_file)
                    self.router.command_queue.put(context)
        except Exception as e:
            print(f"[!] STT Error: {e}")
        finally:
            print(temp_file)

    def _handle_auth(self, sock, username, password):
        stored_password = cfg.DICO_USERS.get(username)
        if stored_password and stored_password == password:
            if username in self.active_sessions.keys():
                self.active_sessions[username].socks.append(sock)
                self.active_sessions[username].last_seen = 0
            else:
                self.active_sessions[username] = UserSession(username, self.user_count)
                self.active_sessions[username].socks.append(sock)
                self.user_count += 1
            print(f"[+] Auth Success: {username} session started.")
            return True
        return False

    def handle_client(self, sock):
        try:
            while True:
                raw_data = sock.recv(4096)
                if not raw_data: break

                parts = raw_data.decode('utf-8').strip().split(":", 2)
                if len(parts) < 2: continue
                print(f"[*] Received: {parts}")

                hw_sig, action = parts[0], parts[1]
                payload = parts[2] if len(parts) > 2 else ""

                if hw_sig not in self.allowed_sigs:
                    sock.sendall(b"ERROR: Unauthorized Hardware")
                    break

                if action == "Auth":
                    user, pwd = payload.split(":", 1)
                    if self._handle_auth(sock, user, pwd):
                        sock.sendall(b"AUTH_SUCCESS")
                elif action == "PTT":
                    self.task_queue.put((self.active_sessions["system"], payload))
                    # sock.sendall(b"STATUS: Queued to System")
                    
                elif action in self.active_sessions.keys():
                    current_session = self.active_sessions[action]
                    if sock in current_session.socks:
                        if payload.startswith("END"):
                            sock.close()
                            continue
                        self.task_queue.put((current_session, payload))
                        # sock.sendall(b"STATUS: Command Queued")
                    else:
                        sock.sendall(b"ERROR: Auth Required")               
        except Exception as e:
            print(f"[!] Connection error: {e}")
        finally:
            for username, session in self.active_sessions.items():
                if username == "system":
                    continue
                if sock in session.socks:
                    session.socks.remove(sock)
                    if not session.socks:
                        session.last_seen = time.time()
                        print(f"[*] {username} détaché. Session maintenue en arrière-plan.")
            sock.close()           

    def run_server(self):
        """Starts the SSL-secured Hub Server"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cfg.PATH_CERT, keyfile=cfg.PATH_KEY)
        context.verify_mode = ssl.CERT_NONE
        context.check_hostname = False
        
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(10)
        print(f"[*] Hub Server active on {self.host}:{self.port} (SSL Secure)")

        try:
            while True:
                newsock, addr = server_sock.accept()
                try:
                    conn = context.wrap_socket(newsock, server_side=True)
                    threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                except ssl.SSLError as e:
                    print(f"[!] SSL Handshake failed: {e}")
        except KeyboardInterrupt:
            print("[*] Server shutting down...")
        finally:
            server_sock.close()

if __name__ == "__main__":
    manager = SessionManager()
    manager.run_server()