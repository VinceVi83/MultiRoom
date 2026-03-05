import os
import subprocess
import time
from Gestion import Ctes
from Gestion.Ctes import RETURN_CODE

class VLControl:
    """
    Controller for VLC media player via HTTP interface.
    Compatible with Linux OS. Requires VLC installation.
    """

    def __init__(self, services, index):
        self.is_initialized = False
        self.process = None
        self.port_ctrl = str(9000 + index)
        self.port_stream = str(19000 + index)
        self.current_path = ""
        self.services = services
        self.playlists = [k.lower() for k in Ctes.playlist.keys()]
        
        # Playback State Flags
        self.random_enabled = False
        self.loop_enabled = False
        self.repeat_enabled = False
        self.is_playing = False
        self.base_request = (
            f"curl --user :test '{Ctes.local_ip}:{self.port_ctrl}/"
            f"requests/status.xml?command="
        )
        self.start_vlc()

    def interpret_vlc_command(self, cmd_tokens):
        """
        Routes incoming commands to simple or complex handlers based on argument count.
        """
        if not cmd_tokens or cmd_tokens[0] not in Ctes.vlc.keys() :
            print("Unknown argument received", cmd_tokens)
            return RETURN_CODE.ERR_INVALID_ARGUMENT
            
        arg_count = len(cmd_tokens)
        if arg_count > 1:
            return self.handle_complex_command(cmd_tokens)
        
        return self.handle_simple_command(cmd_tokens[0])

    # region Complex command
    def handle_complex_command(self, cmd_tokens):
        """
        Handles commands requiring additional parameters (volume, directory, sorting).
        """
        action = cmd_tokens[0]
        if action == 'playlist':
            return self.change_playlist(cmd_tokens[1])
        return RETURN_CODE.ERR_INVALID_ARGUMENT

    def change_playlist(self, target):
        """Changes the active directory or playlist dynamically."""
        if target.startswith('/'):
            final_path = target
        else:
            final_path = Ctes.playlist.get(target.lower(), Ctes.playlist["default"])

        self.execute_curl(f"{self.base_request}pl_empty")
        request_url = f"{self.base_request}{Ctes.vlc['dir']}{final_path}"
        self.execute_curl(request_url)
        return RETURN_CODE.SUCCESS
    # endregion

    # region VLC management
    def execute_curl(self, request_url):
        """Executes the VLC HTTP command via a subprocess curl call."""
        request_url = request_url + "'"
        print(f"Curl VLC : {request_url}")
        subprocess.run(
            request_url, 
            shell=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )

    def handle_simple_command(self, action):
        """Executes basic commands without additional parameters."""
        request_url = f"{self.base_request}{Ctes.vlc[action]}"
        self.execute_curl(request_url)
        return RETURN_CODE.SUCCESS

    def start_vlc(self, path=None):
        """Initializes and launches the VLC process."""
        if path is None:
            path = Ctes.playlist["default"]
            
        self.is_initialized = True
        self.is_playing = True
        self.current_path = path
        
        if self.process:
            return RETURN_CODE.SUCCESS

        # Construction des arguments de la commande
        sout_param = f"#standard{{access=http,mux=ogg,dst={Ctes.local_ip}:{self.port_stream}}}"
        args = [
            "vlc",
            "--loop",
            "--playlist-enqueue",
            path,
            f"--http-port={self.port_ctrl}",
            "--sout", sout_param,
            "-I", "dummy",
            "--extraintf", "http",
            "--http-password", Ctes.cfg.pwd_vlc
        ]
        
        try:
            self.process = subprocess.Popen(
                args, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            print("VLC process started")
            return RETURN_CODE.SUCCESS
        except Exception as e:
            print(f"Error starting VLC: {e}")
            return RETURN_CODE.ERR
        
    def kill_vlc(self):
        """Terminates the VLC process and ensures all states are reset."""
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
        return RETURN_CODE.SUCCESS
    # endregion