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

    def _start_vlc_if_needed(self):
        if self.vlc_instance is None:
            from plugins.music_vlc.vlc_control import VLControl
            self.vlc_instance = VLControl(self.user_index)

    def build_playlist_map(self):
        base_dir = Path(cfg.music_vlc.DATA_DIR) / "Playlists"

        try:
            with os.scandir(base_dir) as entries:
                for entry in entries:
                    name = Path(entry.name).stem.lower()
                    self.playlists[name] = entry.path
            print(base_dir, self.playlists)
        except FileNotFoundError:
            print(f"[!] Error: Directory {base_dir} not found.")

    def interpret_vlc_command(self, context):
        self._start_vlc_if_needed()
        if context.label == "PLAYLIST_AGENT":
            command = context.result.split(":")
            if command[0] == "PLAY":
                target = self.playlists.get(command[1].lower(), self.playlists.get("default"))
                self.vlc_instance.change_playlist(target)
            else:
                return cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED

        elif context.label == "VLC_AGENT":
            return self.vlc_instance.handle_simple_command(context.result)
        
        return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def __del__(self):
        if self.vlc_instance:
            self.vlc_instance.kill_vlc()
