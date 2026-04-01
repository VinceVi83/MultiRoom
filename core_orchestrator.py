import socket
import ssl
import queue
import threading
import os
import requests
import time
import json
import sys
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
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
    """Session Manager
    
    Role: Manages user sessions, task routing, and client connections for the hub system.
    
    Methods:
        __init__(self, disable_whisper=False) : Initialize session manager with optional Whisper STT.
        _cleanup_loop(self) : Background loop for cleaning inactive sessions.
        _do_session_cleanup(self) : Perform cleanup of sessions exceeding timeout.
        _worker_loop(self) : Background worker loop processing task queue.
        _handle_direct_command(self, session, text) : Handle direct text commands from clients.
        _handle_stt_request(self, session, url) : Handle speech-to-text requests via Whisper.
        _handle_auth(self, sock, username, password) : Validate user authentication credentials.
        handle_client(self, sock) : Handle incoming client socket connections.
        run_server(self) : Start the SSL server and accept client connections.
    """
    def __init__(self, disable_whisper=True):
        self.host = "0.0.0.0"
        self.port = int(cfg.sys.config.HUB_PORT)
        self.allowed_sigs = cfg.sys.security.LIST_ALLOWED_SIGS
        self.user_count = 0
        self.active_sessions = {}
        self.disable_whisper = disable_whisper

        if not self.disable_whisper:
            self.whisper = WhisperEngine()
        else:
            self.whisper = None
            
        self.router = RouterLLM()
        self.active_sessions["system"] = UserSession("system", self.user_count)
        self.user_count += 1

        self.task_queue = queue.Queue()
        threading.Thread(target=self._worker_loop, daemon=True).start()
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def _cleanup_loop(self):
        while True:
            try:
                self._do_session_cleanup()
            except Exception as e:
                print(f"[!] Cleanup loop encountered a critical error: {e}")
            time.sleep(300)

    def _do_session_cleanup(self):
        now = time.time()
        for username, session in list(self.active_sessions.items()):
            if username == "system" or session.socks:
                continue

            if now - session.last_seen > 7200:
                try:
                    session.stop_all_services()
                    self.active_sessions.pop(username, None)
                except Exception as e:
                    print(f"[!] Error cleaning session for {username}: {e}")

    def _worker_loop(self):
        while True:
            session, payload = self.task_queue.get()
            try:
                if payload.startswith("https"):
                    self._handle_stt_request(session, payload)
                else:
                    self._handle_direct_command(session, payload)
            except Exception as e:
                print(f"[!] Worker Error: {e}")
            finally:
                self.task_queue.task_done()

    def _handle_direct_command(self, session, text):
        if text:
            context = TaskContext(user_input=text, session=session)
            self.router.add_to_queue(context)

    def _handle_stt_request(self, session, url):
        if self.disable_whisper:
            return
        temp_file = f"/tmp/temp_{session.index}_{threading.get_ident()}.wav"
        try:
            response = requests.get(url, timeout=10, verify=False)
            if response.status_code == 200:
                with open(temp_file, "wb") as f:
                    f.write(response.content)

                text = self.whisper.transcribe(temp_file)
                if text:
                    context = TaskContext(user_input=text, session=session, audio_path=temp_file)
                    self.router.add_to_queue(context)
        except Exception as e:
            print(f"[!] STT Error: {e}")
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def _handle_auth(self, sock, username, password):
        stored_password = getattr(cfg.sys.security.DICO_USERS, username, None)
        if stored_password and stored_password == password:
            if username in self.active_sessions.keys():
                self.active_sessions[username].socks.append(sock)
                self.active_sessions[username].last_seen = 0
            else:
                self.active_sessions[username] = UserSession(username, self.user_count)
                self.active_sessions[username].socks.append(sock)
                self.user_count += 1
            return True
        return False

    def handle_client(self, sock):
        sock.settimeout(7200.0)
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
                    else:
                        sock.sendall(b"ERROR: Auth Failed\n")
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
                    try:
                        session.socks.remove(sock)
                    except (ValueError, AttributeError):
                        pass
                    if not session.socks:
                        session.last_seen = time.time()
            try:
                sock.close()
            except:
                pass

    def run_server(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        dir_cert = Path(cfg.DATA_DIR) / "Certification"
        context.load_cert_chain(certfile=dir_cert/"cert.pem", keyfile=dir_cert/"key.pem")
        context.verify_mode = ssl.CERT_NONE
        context.check_hostname = False

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(10)
        try:
            while True:
                newsock, addr = server_sock.accept()
                try:
                    conn = context.wrap_socket(newsock, server_side=True)
                    threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                except (ssl.SSLError, socket.error) as e:
                    print(f"[!] Connection failed (SSL/Socket): {e}")
                except Exception as e:
                    print(f"[!] Unexpected error in accept loop: {e}")
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self.router.stop()
                server_sock.close()
            except Exception as e:
                print(f"[!] Close Error: {e}")

if __name__ == "__main__":
    no_whisper_flag = "--no-whisper" in sys.argv
    
    manager = SessionManager(no_whisper_flag)
    manager.run_server()
