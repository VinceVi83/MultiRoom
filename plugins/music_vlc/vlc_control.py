import os
import subprocess
import re
import time
from config_loader import cfg
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

    def __init__(self, index, playlist=""):
        self.is_initialized = False
        self.is_playing = False
        self.process = None
        self.index = index
        self.port_ctrl = str(9000 + index)
        self.port_stream = str(19000 + index)
        self.current_path = ""

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

    def handle_simple_command(self, action):
        cmd = self.vlc_commands[action]
        url = f"http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/requests/status.xml?command={cmd}"
        subprocess.run(["curl", "-s", "--user", ":test", url], shell=False, stdout=subprocess.DEVNULL)
        return cfg.RETURN_CODE.SUCCESS

    def change_playlist(self, target):
        empty_url = f"http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/requests/status.xml?command=pl_empty"
        subprocess.run(["curl", "-s", "--user", ":test", empty_url], shell=False, stdout=subprocess.DEVNULL)
        
        play_url = f"http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/requests/status.xml?command=in_play&input={target}"
        subprocess.run(["curl", "-s", "--user", ":test", play_url], shell=False, stdout=subprocess.DEVNULL)
        return cfg.RETURN_CODE.SUCCESS

    def start_vlc(self, path="default"):
        if self.process and self.process.poll() is None:
            return cfg.RETURN_CODE.SUCCESS

        sout_param = f"#standard{{access=http,mux=ogg,dst={cfg.sys.INTERFACE_IP}:{self.port_stream}}}"
        args = [
            "vlc", "--loop", "--playlist-enqueue", path,
            f"--http-port={self.port_ctrl}", "--sout", sout_param,
            "-I", "dummy", "--extraintf", "http", "--http-password", cfg.sys.DICO_USERS[cfg.sys.LIST_USERS[0]]
        ]

        try:
            self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_initialized = True
            self.is_playing = True
            return cfg.RETURN_CODE.SUCCESS
        except:
            return cfg.RETURN_CODE.ERR

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
        return cfg.RETURN_CODE.SUCCESS

    def get_remaining_seconds(self):
        url = f"http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/requests/status.xml"
        current_remaining = 0
        try:
            result = subprocess.run(["curl", "-s", "--user", ":test", url], 
                                   shell=False, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout:
                root = ET.fromstring(result.stdout)
                curr_time = int(root.findtext('time', '0'))
                total_length = int(root.findtext('length', '0'))
                return max(0, total_length - curr_time)
        except:
            return -1

    def get_total_remaining_seconds(self):
        current_remaining = self.get_remaining_seconds()
        url = f"http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/requests/playlist.xml"
        try:
            result = subprocess.run(["curl", "-s", "--user", ":test", url], 
                                   shell=False, capture_output=True, text=True)
            if result.returncode != 0 or not result.stdout:
                return current_remaining
            
            root = ET.fromstring(result.stdout)
            total_after_current = 0
            found_current = False
            
            for leaf in root.iter('leaf'):
                is_current = leaf.get('current') == 'current'
                if is_current:
                    found_current = True
                    continue
                
                if found_current:
                    duration = leaf.get('duration', '0')
                    if duration and int(duration) > 0:
                        total_after_current += int(duration)
                        
            return current_remaining + total_after_current
        except:
            return current_remaining

    def get_current_state(self):
        url = f"http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/requests/status.xml"
        try:
            result = subprocess.run(
                ["curl", "-s", "--user", ":test", url], 
                shell=False, capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout:
                root = ET.fromstring(result.stdout)
                state = root.findtext('state', 'unknown')
                return state.lower()
        except Exception:
            pass
        return "unknown"

    def __del__(self):
        self.kill_vlc()
