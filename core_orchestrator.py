import socket
import ssl
import queue
import threading
import os
import requests
import time
import json
from router_llm import RouterLLM
from tools.scraper import ScraperService
from tools.whisper_engine import WhisperEngine
from config_loader import cfg
from user_session import UserSession
from tools.task_context import TaskContext
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

class SessionManager:
    """
    Manages user sessions and handles incoming requests.

    Methods:
    - __init__(self) : Initializes the session manager.
    - _cleanup_inactive_sessions(self) : Cleans up inactive sessions.
    - _worker_loop(self) : Processes tasks from the queue.
    - _handle_direct_command(self, session, text) : Handles direct commands.
    - _handle_stt_request(self, session, url) : Handles speech-to-text requests.
    - _handle_auth(self, sock, username, password) : Handles user authentication.
    - handle_client(self, sock) : Handles client connections.
    - run_server(self) : Starts the SSL-secured Hub Server.
    """

    def __init__(self):
        self.host = cfg.sys.INTERFACE_IP
        self.port = int(cfg.sys.HUB_PORT)
        self.allowed_sigs = cfg.sys.LIST_ALLOWED_SIGS
        self.user_count = 0
        self.active_sessions = {}

        print("[*] Loading Whisper...")
        self.whisper = WhisperEngine()
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
        if text:
            print(f"[*] Transcription [{session.username}]: {text}")
            context = TaskContext(user_input=text, session=session)
            self.router.add_to_queue(context)

    def _handle_stt_request(self, session, url):
        temp_file = f"/tmp/temp_{session.index}_{threading.get_ident()}.wav"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(temp_file, "wb") as f:
                    f.write(response.content)

                text = self.whisper.transcribe(temp_file)
                if text:
                    print(f"[*] Transcription [{session.username}]: {text}")
                    context = TaskContext(user_input=text, session=session, audio_path=temp_file)
                    self.router.add_to_queue(context)
        except Exception as e:
            print(f"[!] STT Error: {e}")
        finally:
            print(temp_file)

    def _handle_auth(self, sock, username, password):
        stored_password = cfg.sys.DICO_USERS.get(username)
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

                elif action in self.active_sessions.keys():
                    current_session = self.active_sessions[action]
                    if sock in current_session.socks:
                        if payload.startswith("END"):
                            sock.close()
                            continue
                        self.task_queue.put((current_session, payload))
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
                        print(f"[*] {username} detached. Session maintained in background.")
            sock.close()

    def run_server(self):
        """Starts the SSL-secured Hub Server"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        dir_cert = Path(cfg.DATA_DIR) / "Certification"
        context.load_cert_chain(certfile=dir_cert/"cert.pem", keyfile=dir_cert/"key.pem")
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
