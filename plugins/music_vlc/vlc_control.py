import os
import subprocess
import re
import time
from pathlib import Path
import xml.etree.ElementTree as ET
import shlex

class VLCControl:
    """VLC Media Player Control Service
    
    Role: Manages VLC media player control and playlist management.
    
    Methods:
        __init__(self, index, playlist='') : Initialize VLC control instance.
        interpret_vlc_command(self, cmd_tokens) : Interpret and execute VLC commands.
        handle_simple_command(self, action) : Handle simple VLC commands.
        change_playlist(self, target) : Change the current playlist.
        start_vlc(self, path=None) : Start the VLC media player.
        kill_vlc(self) : Terminate the VLC media player.
        get_remaining_seconds(self) : Get remaining seconds for current track.
        get_total_remaining_seconds(self) : Get total remaining seconds in playlist.
        get_current_state(self) : Get current playback state.
        __del__(self) : Cleanup on destruction.
    """

    def __init__(self, cfg, index, playlist=""):
        self.index = index
        self.cfg = cfg
        self.port_ctrl = str(int(self.cfg.VLC_PORT_START) + index)
        self.port_stream = str(int(self.cfg.VLC_PORT_START) + 1000 + index)
        self.password = self.cfg.DICO_VLC_USERS.get('test', 'test')
        self.base_url = f"http://127.0.0.1:{self.port_ctrl}/requests"

        self.process = None
        self.is_initialized = False
        self.is_playing = False
        self.current_path = playlist

        self.vlc_commands = {
            "TOGGLE": "pl_pause",
            "PREVIOUS": "pl_previous",
            "NEXT": "pl_next",
            "VOL_DOWN": "volume&val=-60",
            "VOL_UP": "volume&val=+60",
            "SHUFFLE": "pl_random",
            "INFO": "status.xml",
            "playlist": "",
            'dir': "in_play&input="
        }

        self.start_vlc(playlist)

    def _vlc_request(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        if params:
            url += f"?{params}"
        
        try:
            result = subprocess.run(
                ["curl", "-s", "--user", f":{self.password}", url],
                shell=False, capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout
            else:
                print(f"VLC Error (Code {result.returncode}) on {endpoint}")
        except Exception as e:
            print(f"Request Exception: {e}")
        return None

    def handle_simple_command(self, action):
        cmd = self.vlc_commands.get(action)
        if cmd:
            return self._vlc_request("status.xml", f"command={cmd}")
        return None

    def change_playlist(self, target):
        self._vlc_request("status.xml", "command=pl_empty")
        self.current_path = target
        return self._vlc_request("status.xml", f"command=in_play&input={target}")

    def start_vlc(self, path="default"):
        self.current_path = path
        if self.process and self.process.poll() is None:
            return self.cfg.RETURN_CODE.SUCCESS

        sout_param = f"#standard{{access=http,mux=ogg,dst=0.0.0.0:{self.port_stream}}}"
        args = [
            "vlc", "--loop", "--playlist-enqueue", path,
            f"--http-port={self.port_ctrl}", "--sout", sout_param,
            "-I", "dummy", "--extraintf", "http", "--http-password", self.password
        ]

        try:
            self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_initialized = True
            self.is_playing = True
            return self.cfg.RETURN_CODE.SUCCESS
        except:
            return self.cfg.RETURN_CODE.ERR

    def kill_vlc(self):
        if self.process:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                    self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            finally:
                self.process = None

        self.is_initialized = False
        self.is_playing = False
        self.current_path = ""
        return self.cfg.RETURN_CODE.SUCCESS

    def get_remaining_seconds(self):
        xml_data = self._vlc_request("status.xml")
        if xml_data:
            try:
                root = ET.fromstring(xml_data)
                curr_time = int(root.findtext('time', '0'))
                total_length = int(root.findtext('length', '0'))
                return max(0, total_length - curr_time)
            except Exception:
                return -1
        return -1

    def get_total_remaining_seconds(self):
        current_remaining = self.get_remaining_seconds()
        xml_data = self._vlc_request("playlist.xml")
        
        if not xml_data:
            return current_remaining
            
        try:
            root = ET.fromstring(xml_data)
            total_after_current = 0
            found_current = False
            
            for leaf in root.iter('leaf'):
                if leaf.get('current') == 'current':
                    found_current = True
                    continue
                
                if found_current:
                    duration = leaf.get('duration', '0')
                    if duration and int(duration) > 0:
                        total_after_current += int(duration)
                        
            return current_remaining + total_after_current
        except Exception:
            return current_remaining

    def get_current_state(self):
        xml_data = self._vlc_request("status.xml")
        if xml_data:
            try:
                root = ET.fromstring(xml_data)
                return root.findtext('state', 'unknown').lower()
            except Exception:
                pass
        return "unknown"

    def __del__(self):
        self.kill_vlc()
