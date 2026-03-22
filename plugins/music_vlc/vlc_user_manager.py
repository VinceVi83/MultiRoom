from plugins.music_vlc.vlc_control import VLControl
from config_loader import cfg
from pathlib import Path
import os

class VLCUserManager:
    """
    Manages VLC instance and playlist operations for a specific user session.
    
    Methods:
        __init__(session, user_index) : Initialize the manager with session and user index
        _start_vlc_if_needed() : Start VLC instance if not already running
        build_playlist_map() : Build mapping of playlist names to file paths
        interpret_vlc_command(context) : Interpret and execute VLC commands from context
        __del__() : Cleanup resources when object is destroyed
    """

    def __init__(self, session, user_index):
        self.user_index = user_index
        self.user_session = session
        self.attached = False
        self.vlc_instance = None
        self.playlists = {}
        self.build_playlist_map()

    def is_alive(self):
        if self.vlc_instance and self.vlc_instance.process:
            return self.vlc_instance.process.poll() is None
        return False

    def _start_vlc_if_needed(self, playlist=""):
        if not self.is_alive():
            playlist_path = ""
            if playlist == "" and self.playlists:
                playlist_path = list(self.playlists.values())[0]
            elif playlist in self.playlists:
                playlist_path = self.playlists.get(playlist)
            
            self.vlc_instance = VLControl(self.user_index, playlist_path)
            return True
        return False

    def build_playlist_map(self):
        base_dir = Path(cfg.music_vlc.DATA_DIR) / "Playlists"

        try:
            with os.scandir(base_dir) as entries:
                for entry in entries:
                    name = Path(entry.name).stem.lower()
                    self.playlists[name] = entry.path
        except FileNotFoundError:
            print(f"[!] Error: Directory {base_dir} not found.")

    def interpret_vlc_command(self, context):
        if context.label == "PLAYLIST_AGENT":
            command = context.result.split(":")
            playlist = self.playlists.get(command[1].lower())
            if command[0] == "PLAY":
                if not self._start_vlc_if_needed(playlist):
                    self.vlc_instance.change_playlist(playlist)
                return cfg.RETURN_CODE.SUCCESS
            else:
                return cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED

        elif context.label == "VLC_AGENT":
            if not self._start_vlc_if_needed():
                self.vlc_instance.handle_simple_command(context.result)
            return cfg.RETURN_CODE.SUCCESS
        
        return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def __del__(self):
        if self.vlc_instance:
            self.vlc_instance.kill_vlc()
