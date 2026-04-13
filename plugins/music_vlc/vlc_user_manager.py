import os
import random
import threading
import time
import copy
from pathlib import Path
from tools.utils import SimpleStore
from plugins.music_vlc.vlc_control import VLCControl
from plugins.music_vlc.music_monitor import VLCMonitor
from plugins.music_vlc.playlist_manager import PlaylistManager
import xml.etree.ElementTree as ET
import urllib.parse
import logging
logger = logging.getLogger(__name__)

class VLCUserManager:
    """VLC Music Player Manager
    
    Role: Manages VLC instance, playlist operations, music monitoring, and user session for music playback.
    
    Methods:
        __init__(self, cfg, session, user_index) : Initialize the VLC user manager with configuration and session.
        update_playlist_agent(self) : Update playlist agent prompt with current replace playlist.
        launch_playlist(self, name) : Launch and manage a specific playlist.
        interpret_vlc_command(self, context) : Route VLC commands based on sub-category.
        playlist_format_data(self, context) : Parse and format playlist command data.
        execute_playlist(self, context) : Handle playlist operations (play, create, add, delete, info).
        execute_vlc(self, context) : Handle direct VLC commands (play, pause, next, previous, info).
        manage_monitor_playlist(self, delay=2) : Manage auto-switch playlist logic with delay.
        _auto_switch_logic(self, initial_delay) : Auto-switch between albums when track ends.
        play_random_album(self) : Play a random album not in recently played list.
        _schedule_cache_update(self) : Schedule playlist cache update timer.
        _update_playlist_cache(self, path=None) : Update playlist cache from VLC XML data.
        is_alive(self) : Check if VLC instance is running.
        _start_vlc_if_needed(self, path="") : Start VLC instance if not running.
        build_playlist_map(self) : Build mapping of playlist directories to paths.
        _init_album_cache(self) : Initialize album cache from SMB directories.
        print_playlist_summary(self) : Print playlist cache summary to console.
        stop(self) : Stop VLC instance and cleanup resources.
        __del__(self) : Destructor cleanup method.
    """
    def __init__(self, cfg, session, user_index):
        self.user_index = user_index
        self.user_session = session
        self.cfg = cfg
        self.vlc_instance = None
        self.current_album_name = ""
        self.replace_playlist = ""
        self.playlist_prompt_o = copy.deepcopy(self.cfg.PLAYLIST_AGENT.prompt)
        self.playlist_agent = copy.deepcopy(self.cfg.PLAYLIST_AGENT)

        history_path = Path(self.cfg.DATA_DIR) / self.user_session.username / f"history_user_{user_index}.json"
        self.store = SimpleStore(history_path, default_structure={"recently_played": []})
        self.recently_played = self.store.get("recently_played")
        self.smb_base = self.cfg.config.SMB_MOUNT_POINT
        self.album_cache = []
        self._init_album_cache()

        self.vlc_monitor = VLCMonitor(self)
        self.base_dir_playlist = Path(self.cfg.DATA_DIR) / self.user_session.username / "Playlists"
        self.playlist_manager = PlaylistManager(self.base_dir_playlist)

        self.playlists = {}
        self.build_playlist_map()
        
    def update_playlist_agent(self):
        tmp = self.playlist_prompt_o.replace('REPLACE_PLAYLISTS', self.replace_playlist)
        self.playlist_agent.prompt = tmp
    
    def launch_playlist(self, target):
        if not self._start_vlc_if_needed(target):
            self.vlc_instance.change_playlist(target)
        self.vlc_monitor.trigger_update()
        return self.cfg.RETURN_CODE.SUCCESS

    def interpret_vlc_command(self, context):
        if context.sub_category == "DISCOVER":
            return self.play_random_album()
        elif context.sub_category == "PLAYLIST":
            return self.execute_playlist(context)
        elif context.sub_category == "MUSIC":
            return self.execute_vlc(context)
        return self.cfg.RETURN_CODE.SUCCESS

    def playlist_format_data(self, context):
        action = None 
        name = None
        try:
            data = context.result.split(":")
            if len(data) < 2:
                return self.cfg.RETURN_CODE.ERR
        except (ValueError, AttributeError):
            return self.cfg.RETURN_CODE.ERR
        action = data[0]
        name = data[1].lower()
        for playlist in self.playlists.keys():
            if playlist in context.user_input.lower():
                name = playlist
        return action, name

    def execute_playlist(self, context):
        if not context or not context.result:
            return self.cfg.RETURN_CODE.ERR
        
        action, name = self.playlist_format_data(context)
        context.result = f'{action}:{name}'
        if action == "PLAY":
            playlist_path = self.playlists.get(name, "default")
            self.current_album_name = name
            self.launch_playlist(playlist_path)
            self.vlc_instance.set_vlc_loop(True)
            return "Done"
        elif action == "CREATE" and name:
            res = self.playlist_manager.create_playlist(name)
            if res:
                self.replace_playlist += f', {name}'
                self.playlists[name.lower()] = res
                self.update_playlist_agent()
                return "Done"
            return "Failed"
        elif action == "ADD" and name:
            return self.playlist_manager.add_music(name, self.vlc_monitor.full_path)
        elif action == "DEL" and name:
            return self.playlist_manager.delete_music(name, self.vlc_monitor.full_path)
        elif action == "INFO" and name:
            self.vlc_monitor._sync_playlist_data()
            self.vlc_monitor.print_playlist_summary()
            return "Done"
        return self.cfg.RETURN_CODE.ERR

    def execute_vlc(self, context):
        if not self._start_vlc_if_needed():
            if context.result in "INFO":
                self.vlc_monitor.update_track_info()
                self.vlc_monitor.print_current_track()
                return self.cfg.RETURN_CODE.SUCCESS

            self.vlc_instance.handle_simple_command(context.result)
            if context.result in "TOGGLE":
                self.vlc_monitor.trigger_update()
                return self.cfg.RETURN_CODE.SUCCESS

            if context.result in ["NEXT", "PREVIOUS"]:
                self.vlc_monitor.trigger_update()
            return self.cfg.RETURN_CODE.SUCCESS
        return self.cfg.RETURN_CODE.ERR

    def play_random_album(self):
        if not self.album_cache:
            return self.cfg.RETURN_CODE.ERROR

        if self.vlc_monitor:
            self.vlc_monitor.stop_event.set()

        selection = random.choice(self.album_cache)
        attempts = 0
        while os.path.basename(selection) in self.recently_played and attempts < 20:
            selection = random.choice(self.album_cache)
            attempts += 1

        self.current_album_name = os.path.basename(selection)
        res = self.launch_playlist(selection)
        self.vlc_instance.set_vlc_loop(False)
        self.vlc_monitor = VLCMonitor(self)
        self.vlc_monitor.start()
        return res

    def is_alive(self):
        return self.vlc_instance and self.vlc_instance.process.poll() is None

    def _start_vlc_if_needed(self, path=""):
        if not self.is_alive():
            if not path and self.playlists:
                path = list(self.playlists.values())[0]
            self.vlc_instance = VLCControl(self.cfg, self.user_index, str(path))
            self.vlc_monitor.vlc_instance = self.vlc_instance
            self.vlc_monitor.start()
            return True
        return False

    def build_playlist_map(self):
        try:
            with os.scandir(self.base_dir_playlist) as entries:
                for i, entry in enumerate(entries, 1):
                    basename = Path(entry.name).stem.lower()
                    self.playlists[basename] = entry.path
            self.replace_playlist = ", ".join(self.playlists.keys())
            self.update_playlist_agent()
        except FileNotFoundError:
            pass

    def _init_album_cache(self):
        for directory in self.smb_base:
            if os.path.exists(directory):
                self._append_album_cache(directory)

        if not self.album_cache:
            logger.error(f"No Music collection")
            return False
        return True
    
    def _append_album_cache(self, directory):
        with os.scandir(directory) as it:
            for entry in it:
                if entry.is_dir():
                    self.album_cache.append(entry.path)

    def stop(self):
        if self.vlc_monitor:
            self.vlc_monitor.stop()
            
        if self.vlc_instance:
            self.vlc_instance.kill_vlc()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
