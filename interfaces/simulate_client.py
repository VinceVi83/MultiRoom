import os
import socket
import ssl
import json
import threading
import time
import hashlib
import platform
import subprocess
import argparse
import sys
from tools.task_context import TaskContext
from http.server import SimpleHTTPRequestHandler, HTTPServer
from config_loader import cfg
from pathlib import Path


class STTSimulator:
    """
    Simulates a text-to-speech system for testing purposes.

    Methods:
        __init__(http_port, json_path) : Initializes the simulator instance and sets default attributes.
        check_result(response) : Validates if the received response matches expected task context data.
        get_hardware_signature() : Generates a unique hardware signature for authentication.
        load_and_verify() : Loads JSON records and verifies existence of associated audio files.
        connect_hub(timeout=60) : Establishes a secure SSL connection to the central hub.
        _send_packet(message, label) : Encodes and transmits data packets to the hub, handling responses.
        authenticate() : Performs initial authentication with the hub using the signature.
        _serve_file() : Starts a temporary HTTP server to serve audio files for recording.
        send_to_hub(entry, mode) : Constructs and sends PTT or text commands to the hub.
        interactive_mode(mode) : Runs the simulator allowing manual selection of test records.
        auto_mode(mode) : Automatically iterates through all available test records sequentially.
    """

    def __init__(self):
        self.http_port = 8090
        self.json_path = Path(cfg.sys.DIR_DOCS) / "Recording/record.json"
        self.records = []
        self.current_idx = 0
        self.signature = self.get_hardware_signature()
        self.client_socket = None
        self.authenticated = False
        self.current_object = None

    def check_result(self, response):
        try:
            context = TaskContext.from_json(response)
            exp = self.current_object
            if not exp:
                print("   [!] Error : No expected object (current_object) found.")
                return False

            actual_cat = context.category
            actual_sub = context.label
            actual_loc = context.location
            actual_res = context.result

            exp_cat = exp.get('Category', 'NONSENSE')
            exp_sub = exp.get('Subcategory', 'NONSENSE')
            exp_loc = exp.get('Location', 'NONSENSE')
            exp_res = exp.get('Result', 'NONSENSE')

            data_match = (
                actual_cat == exp_cat and
                actual_sub == exp_sub and
                actual_loc.lower() == exp_loc.lower() and
                actual_res.lower() == exp_res.lower()
            )

            if data_match:
                print(f"   [OK] Perfect match : {actual_cat} | {actual_sub} | {actual_loc} | {actual_res}")
                return True
            else:
                print("-" * 30)
                print(f"\n   [X] Match failure for: '{context.user_input}'")
                print(f"       Expected: {exp_cat} | {exp_sub} | {exp_loc} | {exp_res}")
                print(f"       Obtained: {actual_cat} | {actual_sub} | {actual_loc} | {actual_res}")
                print("-" * 30)
                return False

        except Exception as e:
            print(f"   [!] Error check_result : {e}")
            return False

    def get_hardware_signature(self):
        try:
            cmd = ['wmic.exe', 'csproduct', 'get', 'uuid']
            if platform.system() != "Windows" and subprocess.run(['which', 'wmic.exe'], capture_output=True).returncode != 0:
                with open("/etc/machine-id", "r") as f:
                    os_id = f.read().strip()
            else:
                os_id = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                os_id = os_id.decode('utf-8').split('\n')[1].strip().replace('\r', '')

            raw_signature = f"{platform.node()}-{os_id}"
            return hashlib.sha256(raw_signature.encode()).hexdigest()
        except Exception:
            return hashlib.sha256(platform.node().encode()).hexdigest()

    def load_and_verify(self):
        if not os.path.exists(self.json_path):
            print(f"[!] Error : {self.json_path} not found."); sys.exit(1)
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.records = json.load(f)
        except Exception as e:
            print(f"[!] JSON Error : {e}"); sys.exit(1)

        print(f"[*] Verifying {len(self.records)} entries...")
        for entry in self.records:
            fname = Path(cfg.sys.DIR_DOCS) / "Recording" / entry.get('Filename')
            if fname and not os.path.exists(fname):
                print(f"[!] Missing audio file : {fname}")

    def connect_hub(self, timeout=60):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try:
            raw_sock = socket.create_connection((cfg.sys.HUB_IP, cfg.sys.HUB_PORT), timeout=timeout)
            self.client_socket = context.wrap_socket(raw_sock, server_hostname=cfg.sys.HUB_IP)
            return True
        except Exception as e:
            print(f"[!] Connection error: {e}")
            return False

    def _send_packet(self, message, label):
        if not self.client_socket:
            if not self.connect_hub(): return None
        try:
            self.client_socket.sendall(message.encode('utf-8'))
            response = self.client_socket.recv(4096).decode('utf-8')
            if self.debug:
                print(f"[{label}] Hub Response : {response}")
            return response
        except Exception as e:
            print(f"[!] Transmission error : {e}")
            self.client_socket = None
            return None

    def authenticate(self):
        auth_packet = f"{self.signature}:Auth:{cfg.sys.LIST_USERS[0]}:{cfg.sys.DICO_USERS[cfg.sys.LIST_USERS[0]]}"
        if self._send_packet(auth_packet, "AUTH"):
            self.authenticated = True

    def _serve_file(self):
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args): pass
        try:
            server = HTTPServer(('0.0.0.0', self.http_port), QuietHandler)
            server.handle_request()
        except: pass

    def send_to_hub(self, entry, mode):
        self.current_object = entry

        if mode == "audio":
            local_ip = socket.gethostbyname(socket.gethostname())
            url = f"http://{local_ip}:{self.http_port}/{entry['Filename']}"
            packet = f"{self.signature}:PTT:{url}"
            threading.Thread(target=self._serve_file, daemon=True).start()
        else:
            packet = f"{self.signature}:test:{entry['Command']}"
        if self.debug:
            print(f"\n>> [{self.current_idx}] SEND : {entry['Command']}")
        self._send_packet(packet, mode.upper())

    def interactive_mode(self, mode):
        print(f"\n--- INTERACTIVE MODE ({mode.upper()}) ---")
        self.current_object = self.records[self.current_idx]

        while self.current_idx < len(self.records):
            choice = input(f"ID [{self.current_idx}/{len(self.records)-1}] (n/q/ID) > ").strip().lower()
            if choice == 'q': break
            elif choice == 'n':
                self.current_idx += 1
                if self.current_idx < len(self.records):
                    self.send_to_hub(self.records[self.current_idx], mode)
            elif choice == '': self.send_to_hub(self.records[self.current_idx], mode)
            else:
                try:
                    self.current_idx = int(choice)
                    self.send_to_hub(self.records[self.current_idx], mode)
                except: pass

    def auto_mode(self, mode):
        for i, entry in enumerate(self.records):
            self.current_idx = i
            self.current_object = entry
            self.send_to_hub(entry, mode)
            time.sleep(1.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("-a", "--audio", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    args = parser.parse_args()

    mode = "audio" if args.audio else "text"
    
    sim = STTSimulator()
    sim.debug = args.debug
    sim.load_and_verify()

    if sim.connect_hub():
        sim.authenticate()
        if args.interactive: sim.interactive_mode(mode)
        else:
            sim.auto_mode(mode)
