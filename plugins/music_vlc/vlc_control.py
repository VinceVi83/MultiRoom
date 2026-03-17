import os
import subprocess
import re
import time
from config_loader import cfg
from pathlib import Path


class VLControl:
    """VLC Media Player Control Service.

    Manages VLC media player control and playlist management.

    Methods:
        __init__(services, index) : Initializes the VLC control instance.
        _escape_path(text) : Escapes special characters in a path string.
        interpret_vlc_command(cmd_tokens) : Interprets and executes VLC commands.
        handle_simple_command(action) : Handles simple VLC commands.
        change_playlist(target) : Changes the current playlist.
        start_vlc(path=None) : Starts the VLC media player.
        kill_vlc() : Terminates the VLC media player.
    """

    def __init__(self, services, index):
        self.is_initialized = False
        self.is_playing = False
        self.process = None
        self.services = services
        self.index = index
        self.port_ctrl = str(9000 + index)
        self.port_stream = str(19000 + index)
        self.current_path = ""

        self.vlc_commands = {
            "1": "pl_pause",
            "2": "pl_previous",
            "3": "pl_next",
            "4": "volume&val=-30",
            "5": "volume&val=+30",
            "6": "pl_random",
            "7": "status.xml",
            "playlist": "",
            'dir': "in_play&input="
        }

        self.playlist_map = {
            "touhou": f"{cfg.sys.DIR_DOCS}/Playlists/touhou",
            "rock": f"{cfg.sys.DIR_DOCS}/Playlists/rock",
        }

        self.base_request = (
            f"curl -s --user :test 'http://{cfg.sys.INTERFACE_IP}:{self.port_ctrl}/"
            f"requests/status.xml?command="
        )
        self.start_vlc()

    def _escape_path(self, text):
        return re.escape(text)

    def interpret_vlc_command(self, cmd_tokens):
        if not cmd_tokens or cmd_tokens[0] not in self.vlc_commands:
            return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

        action = cmd_tokens[0].lower()
        if action == 'playlist' and len(cmd_tokens) > 1:
            return self.change_playlist(cmd_tokens[1])

        return self.handle_simple_command(action)

    def handle_simple_command(self, action):
        request_url = f"{self.base_request}{self.vlc_commands[action]}'"
        subprocess.run(request_url, shell=True, stdout=subprocess.DEVNULL)
        return cfg.RETURN_CODE.SUCCESS

    def change_playlist(self, target):
        final_path = cfg.PLAYLIST_LIST["Default"]
        subprocess.run(f"{self.base_request}pl_empty'", shell=True, stdout=subprocess.DEVNULL)
        path_esc = self._escape_path(final_path)
        request_url = f"{self.base_request}{self.vlc_commands['dir']}{path_esc}'"
        subprocess.run(request_url, shell=True, stdout=subprocess.DEVNULL)
        return cfg.RETURN_CODE.SUCCESS

    def start_vlc(self, path=None):
        if self.process and self.process.poll() is None:
            return cfg.RETURN_CODE.SUCCESS

        path = path if path else self.playlist_map["touhou"]
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
