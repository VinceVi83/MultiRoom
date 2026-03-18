from plugins.music_vlc.vlc_control import VLControl
from config_loader import cfg
from pathlib import Path
import os

class VLCUserManager:
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
            print(f"[!] Erreur : Dossier {base_dir} introuvable.")

    def interpret_vlc_command(self, context):
        """
        "PAUSE": "pl_pause",
        "PREV": "pl_previous",
        "NEXT": "pl_next",
        "VOL_DOWN": "volume&val=-30",
        "VOL_UP": "volume&val=+30",
        "SHUFFLE": "pl_random",
        "INFO": "status.xml",
        """

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