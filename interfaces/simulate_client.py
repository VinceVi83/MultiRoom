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
from interfaces.voice_node import UnifiedSpeechSystem

class STTSimulator(UnifiedSpeechSystem):
    """STTSimulator
    
    Role: Simulates a text-to-speech system for testing purposes including authentication, packet transmission, and audio file serving.
    
    Methods:
        __init__(self, path, mode, is_linux) : Initialize the simulator instance with configuration parameters.
        check_result(self, response) : Validate if received response matches expected task context data.
        load_and_verify(self) : Load JSON records and verify existence of associated audio files.
        send_to_hub(self, entry) : Construct and send PTT or text commands to the hub.
        interactive_mode(self) : Run simulator allowing manual selection of test records.
        auto_mode(self) : Automatically iterate through all available test records sequentially.
    """

    def __init__(self, path, mode, is_linux=False):
        self.http_port = 8090
        self.json_path = Path(path)
        self.records = []
        self.mode = mode
        self.current_idx = 0
        self.debug = True
        self.client_socket = None
        self.authenticated = False
        self.current_object = None
        self.ssock = None
        self.running = True
        self.hw_signature = self._get_hw_sign()

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
            actual_code = context.return_code

            exp_cat = exp.get('Category', 'NONSENSE')
            exp_sub = exp.get('Subcategory', 'NONSENSE')
            exp_loc = exp.get('Location', 'NONSENSE')
            exp_res = exp.get('Result', 'NONSENSE')
            exp_code = exp.get('ReturnCode', 'ReturnCode.ERR')

            data_match = (
                actual_cat == exp_cat and
                actual_sub == exp_sub and
                actual_loc.lower() == exp_loc.lower() and
                actual_res.lower() == exp_res.lower() and
                actual_code == exp_code
            )

            if data_match:
                print(f"   [OK] Perfect match : {actual_cat} | {actual_sub} | {actual_loc} | {actual_res}")
                return True
            else:
                sep = "─" * 80
                header = f"{'TYPE':<12} | {'CATEGORY':<15} | {'SUBCAT':<15} | {'LOC':<15} | {'CODE':<15} | {'RES'}"

                print(f"\n! MISMATCH DETECTED")
                print(f"Input: '{context.user_input}'")
                print(sep)
                print(header)
                print(sep)

                print(f"{'OBTAINED':<12} | {actual_cat:<15} | {actual_sub:<15} | {actual_loc:<15} | {actual_code:<15} | {actual_res:<15}")
                print(f"{'EXPECTED':<12} | {exp_cat:<15} | {exp_sub:<15} | {exp_loc:<15} | {exp_code:<15} | {exp_res:<15}")
                print(sep)
                return False

        except Exception as e:
            print(f"   [!] Error check_result : {e}")
            return False

    def load_and_verify(self):
        if not self.json_path.exists():
            print(f"[!] Error : {self.json_path} not found."); sys.exit(1)
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.records = json.load(f)
        except Exception as e:
            print(f"[!] JSON Error : {e}"); sys.exit(1)

        print(f"[*] Verifying {len(self.records)} entries...")
        base_path = self.json_path.parent
        
        for entry in self.records:
            fname = entry.get('audio_path')
            if fname:
                full_path = base_path / fname
                if not full_path.exists():
                    print(f" [!] Missing audio file : {fname}")

    def send_to_hub(self, entry):
        self.current_object = entry
        
        if self.mode == "ptt":
            filename = entry.get('audio_path') 
            if not filename: return

            audio_dir = self.json_path.parent
            os.chdir(audio_dir) 

            url = f"https://127.0.0.1:{self.http_port}/{filename}"
            print(f"[*] Serving: {url}")

            threading.Timer(0.5, lambda: self.send_packet("PTT", url)).start()

            try:
                server_address = ('0.0.0.0', self.http_port)
                httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
                ctx = self._get_https_server_context() 
                httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
                
                httpd.handle_request()
                httpd.server_close()
            except Exception as e:
                print(f"[!] Error : {e}")
        
        else:
            if self._ensure_stt_connection():
                response = self.send_packet("test", entry['Command'])
                if response:
                    self.check_result(response)

    def interactive_mode(self):
        print(f"\n--- INTERACTIVE MODE ({self.mode.upper()}) ---")
        self.current_object = self.records[self.current_idx]

        while self.current_idx < len(self.records):
            choice = input(f"ID [{self.current_idx}/{len(self.records)-1}] (n/q/ID) > ").strip().lower()
            if choice == 'q': break
            elif choice == 'n':
                self.current_idx += 1
                if self.current_idx < len(self.records):
                    self.send_to_hub(self.records[self.current_idx])
            elif choice == '': self.send_to_hub(self.records[self.current_idx])
            else:
                try:
                    self.current_idx = int(choice)
                    self.send_to_hub(self.records[self.current_idx])
                except: pass

    def auto_mode(self):
        for i, entry in enumerate(self.records):
            self.current_idx = i
            self.current_object = entry
            self.send_to_hub(entry)
            time.sleep(1.5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, nargs='?', default=".", help="Principal path to data")
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("-m", "--mode", choices=['stt', 'ptt'], required=True, help="Mode: stt (Whisper) or ptt (WAV)")
    parser.add_argument("-L", "--linux", action="store_true", help="Force Linux mode")
    
    args = parser.parse_args()
    
    sim = STTSimulator(args.path, mode=args.mode, is_linux=args.linux)
    sim.load_and_verify()

    if args.interactive: sim.interactive_mode()
    else:
        sim.auto_mode()
