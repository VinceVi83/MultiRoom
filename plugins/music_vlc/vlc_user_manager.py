import os
import random
import threading
import time
from pathlib import Path
from config_loader import cfg
from tools.utils import SimpleStore
from plugins.music_vlc.vlc_control import VLCControl
from plugins.music_vlc.music_monitor import MusicMonitor
from plugins.music_vlc.playlist_manager import PlaylistManager

class VLCUserManager:
    """VLC User Manager
    
    Role: Manages VLC playback with Smart Shuffle Jukebox and persistent history.
    
    Methods:
        __init__(self, session, user_index) : Initialize manager with session and user index.
        _get_albums(self) : Cache list of directories from SMB mount.
        _auto_switch_logic(self, current_album) : Wait for album to finish, save to history, trigger next.
        play_random_album(self) : Pick new album, reset monitor thread, start playback.
        is_alive(self) : Check if VLC instance is running.
        _start_vlc_if_needed(self, path="") : Start VLC if not already running.
        get_total_playlist_duration(self) : Sum of all track durations in current playlist.
        build_playlist_map(self) : Build map of playlist names to paths.
        interpret_vlc_command(self, context) : Router for AI agent commands.
        stop(self) : Stop auto-switch thread and cleanup.
    """
    def __init__(self, session, user_index):
        self.user_index = user_index
        self.user_session = session
        self.vlc_instance = None
        
        self.auto_switch_thread = None
        self.stop_event = threading.Event()
        
        history_path = Path(cfg.music_vlc.DATA_DIR) / f"history_user_{user_index}.json"
        self.store = SimpleStore(history_path, default_structure={"recently_played": []})
        self.recently_played = self.store.get("recently_played")
        
        self.music_monitor = MusicMonitor(user_index)
        self.playlist_manager = PlaylistManager()
        
        self.album_cache = []
        self.current_album_name = ""
        self.max_memory = 50 
        self.smb_base = cfg.music_vlc.SMB_MOUNT_POINT
        
        self.playlists = {}
        self.build_playlist_map()

    def interpret_vlc_command(self, context):
        if context.label == "DISCOVERY":
            return self.play_random_album()
        elif context.label == "PLAYLIST_AGENT":
            return self.execute_playlist(context)
        elif context.label == "VLC_AGENT":
            return self.execute_vlc(context)
        return cfg.RETURN_CODE.SUCCESS

    def execute_playlist(self, context):
        command = context.result.split(":")
        path = self.playlists.get(command[1].lower())
        if command[0] == "PLAY" and path:
            self.stop_event.set()
            if not self._start_vlc_if_needed(path):
                self.vlc_instance.change_playlist(path)
            self.manage_monitor_playlist()
            return cfg.RETURN_CODE.SUCCESS
        return cfg.RETURN_CODE.ERR

    def execute_vlc(self, context):
        if not self._start_vlc_if_needed():
            if self.vlc_instance.get_current_state() == "playing":
                self.stop_event.set()
            else:
                self.stop_event.clear()

            self.vlc_instance.handle_simple_command(context.result)
            if context.result in ["NEXT", "PREVIOUS"]:
                self.music_monitor.force_update()
                self.manage_monitor_playlist()
            return cfg.RETURN_CODE.SUCCESS
        return cfg.RETURN_CODE.ERR

    def manage_monitor_playlist(self, delay=2):
        self.stop_event.set()
        if self.auto_switch_thread and self.auto_switch_thread.is_alive():
            if threading.current_thread() != self.auto_switch_thread:
                self.auto_switch_thread.join(timeout=3)
        
        self.stop_event.clear()
        self.auto_switch_thread = threading.Thread(
            target=self._auto_switch_logic, 
            args=[delay], 
            daemon=True
        )
        self.auto_switch_thread.start()

    def _auto_switch_logic(self, initial_delay):
        if not self.vlc_instance: return
        if self.stop_event.wait(timeout=initial_delay):
            return
        remaining = self.vlc_instance.get_total_remaining_seconds()
        if remaining > 1:
            interrupted = self.stop_event.wait(timeout=remaining - 1)
            if interrupted:
                return

        if self.current_album_name not in self.recently_played:
            self.recently_played.append(self.current_album_name)
            if len(self.recently_played) > self.max_memory:
                self.recently_played.pop(0)
            self.store.update_and_save("recently_played", self.recently_played)

        self.play_random_album()

    def play_random_album(self):
        all_albums = self._get_albums()
        if not all_albums: return cfg.RETURN_CODE.ERR_FILE_NOT_FOUND

        available = [
            a for a in all_albums 
            if os.path.basename(a) not in self.recently_played
        ]
        
        if not available: 
            self.recently_played = []
            available = all_albums
            self.store.update_and_save("recently_played", [])

        selection = random.choice(available)
        album_name = os.path.basename(selection)
        if not self._start_vlc_if_needed(selection):
            self.vlc_instance.change_playlist(selection)

        self.current_album_name = album_name
        self.manage_monitor_playlist()
        
        return cfg.RETURN_CODE.SUCCESS

    def is_alive(self):
        return self.vlc_instance and self.vlc_instance.process.poll() is None

    def _start_vlc_if_needed(self, path=""):
        if not self.is_alive():
            if not path and self.playlists:
                path = list(self.playlists.values())[0]
            self.vlc_instance = VLCControl(self.user_index, str(path))
            self.music_monitor.update_status()
            return True
        return False

    def build_playlist_map(self):
        base_dir = Path(cfg.music_vlc.DATA_DIR) / "Playlists"
        try:
            with os.scandir(base_dir) as entries:
                for entry in entries:
                    self.playlists[Path(entry.name).stem.lower()] = entry.path
        except FileNotFoundError: pass

    def _get_albums(self):
        if not self.album_cache and os.path.exists(self.smb_base):
            self.album_cache = [f.path for f in os.scandir(self.smb_base) if f.is_dir()]
        return self.album_cache

    def stop(self):
        if self.auto_switch_thread:
            self.auto_switch_thread.join(timeout=3)
        if self.vlc_instance:
            self.vlc_instance.kill()

    def __del__(self):
        self.stop()
        if self.vlc_instance:
            self.vlc_instance.kill()
