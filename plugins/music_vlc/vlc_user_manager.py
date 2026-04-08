import os
import random
import threading
import time
from pathlib import Path
from tools.utils import SimpleStore, Utils
from plugins.music_vlc.vlc_control import VLCControl
from plugins.music_vlc.music_monitor import MusicMonitor
from plugins.music_vlc.playlist_manager import PlaylistManager
import urllib.parse

class VLCUserManager:
    """VLC Music Player Manager
    
    Role: Manages VLC instance, playlist operations, music monitoring, and user session for music playback.
    
    Methods:
        __init__(self, cfg, session, user_index) : Initialize the VLC user manager with configuration and session.
        interpret_vlc_command(self, context) : Route VLC commands based on sub-category (DISCOVER, PLAYLIST, MUSIC).
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
        print_playlist_summary(self) : Print playlist cache summary to console.
        stop(self) : Stop VLC instance and cleanup resources.
        __del__(self) : Destructor cleanup method.
    """
    def __init__(self, cfg, session, user_index):
        self.user_index = user_index
        self.user_session = session
        self.cfg = cfg
        self.smb_base = self.cfg.config.SMB_MOUNT_POINT
        history_path = Path(self.cfg.DATA_DIR) / f"history_user_{user_index}.json"
        self.store = SimpleStore(history_path, default_structure={"recently_played": []})
        self.music_monitor = MusicMonitor(self.cfg, user_index)
        self.base_dir_playlist = Path(self.cfg.DATA_DIR) / "Playlists"
        self.playlist_manager = PlaylistManager(self.base_dir_playlist)

        self.vlc_instance = None
        self.current_album_name = ""
        self.album_cache = []
        self.playlists = {}
        self.current_playlist_files = {}
        self.recently_played = self.store.get("recently_played")
        self.build_playlist_map()
        self._init_album_cache()
        self.total_duration_sec = 0

        self.stop_event = threading.Event()
        self.auto_switch_thread = None
        self.cache_timer = None

    def interpret_vlc_command(self, context):
        if context.sub_category == "DISCOVER":
            return self.play_random_album()
        elif context.sub_category == "PLAYLIST":
            return self.execute_playlist(context)
        elif context.sub_category == "MUSIC":
            return self.execute_vlc(context)
        return self.cfg.RETURN_CODE.SUCCESS

    def execute_playlist(self, context):
        if not context or not context.result:
            return self.cfg.RETURN_CODE.ERR
        
        try:
            data = dict(item.split(":") for item in context.result.split(","))
        except (ValueError, AttributeError):
            return self.cfg.RETURN_CODE.ERR
        
        action = data.get("ACTION")
        name = data.get("NAME", "").lower()
        playlist_path = self.playlists.get(name, "default")
        
        if playlist_path and os.path.isdir(playlist_path):
            target = str(playlist_path)
        else:
            target = playlist_path

        if action == "PLAY" and playlist_path != "Unknown":
            self.stop_event.set()
            if not self._start_vlc_if_needed(target):
                self.vlc_instance.change_playlist(target)
            self.manage_monitor_playlist()
            self._schedule_cache_update()
            return self.cfg.RETURN_CODE.SUCCESS
        elif action == "CREATE" and name:
            return self.playlist_manager.create_playlist(name)
        elif action == "ADD" and name:
            return self.playlist_manager.add_music(name, self.music_monitor.full_path)
        elif action == "DEL" and name:
            return self.playlist_manager.delete_music(name, self.music_monitor.full_path)
        elif action == "INFO" and name:
            return self.playlist_manager.delete_music(name, self.music_monitor.full_path)

        return self.cfg.RETURN_CODE.ERR

    def execute_vlc(self, context):
        if not self._start_vlc_if_needed():
            if self.vlc_instance and self.vlc_instance.get_current_state() == "playing":
                self.stop_event.set()
            else:
                self.stop_event.clear()

            if context.result in "INFO":
                self.music_monitor.force_update()
                self.music_monitor.print_status()
                return self.cfg.RETURN_CODE.SUCCESS

            self.vlc_instance.handle_simple_command(context.result)
            if context.result in ["NEXT", "PREVIOUS"]:
                self.music_monitor.force_update()
                self.manage_monitor_playlist()
            return self.cfg.RETURN_CODE.SUCCESS
        return self.cfg.RETURN_CODE.ERR

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
        if not self.vlc_instance:
            return
        if self.stop_event.wait(timeout=initial_delay):
            return
        remaining = self.vlc_instance.get_total_remaining_seconds()
        if remaining > 1:
            interrupted = self.stop_event.wait(timeout=remaining - 1)
            if interrupted:
                return

        if self.current_album_name not in self.recently_played:
            self.recently_played.append(self.current_album_name)
            if len(self.recently_played) > int(self.cfg.config.LEN_ALBUMS_CACHE):
                self.recently_played.pop(0)
            self.store.update_and_save("recently_played", self.recently_played)

        self.play_random_album()

    def play_random_album(self):
        if not self.album_cache:
            return self.cfg.RETURN_CODE.ERR_FILE_NOT_FOUND
        
        available = []
        for a in self.album_cache:
            if os.path.basename(a) not in self.recently_played:
                available.append(a)
        
        if not available: 
            self.recently_played = []
            available = self.album_cache
            self.store.update_and_save("recently_played", [])

        selection = random.choice(available)
        album_name = os.path.basename(selection)
        if not self._start_vlc_if_needed(selection):
            self.vlc_instance.change_playlist(selection)

        self.current_album_name = album_name
        self.manage_monitor_playlist()
        self._schedule_cache_update()
        return self.cfg.RETURN_CODE.SUCCESS
    
    def _schedule_cache_update(self):
        if self.cache_timer:
            self.cache_timer.cancel()
        
        self.cache_timer = threading.Timer(10.0, self._update_playlist_cache)
        self.cache_timer.start()

    def _update_playlist_cache(self, path=None):
        if not self.vlc_instance:
            return

        self.cache_timer = None
        self.current_playlist_files = {}
        total_duration_sec = 0
        new_cache = {}
        xml_data = self.vlc_instance._vlc_request("playlist.xml")
        
        if xml_data:
            try:
                import xml.etree.ElementTree as ET
                import urllib.parse
                root = ET.fromstring(xml_data)
                
                for leaf in root.iter('leaf'):
                    name = leaf.get('name')
                    uri = leaf.get('uri')
                    duration = leaf.get('duration')
                    
                    if name and uri:
                        clean_path = urllib.parse.unquote(uri.replace("file://", ""))
                        new_cache[name] = clean_path
                        if duration and duration.isdigit():
                            total_duration_sec += int(duration)
                
                self.current_playlist_files = new_cache
                self.music_monitor.playlist_cache = new_cache
                self.total_duration_sec = total_duration_sec
                self.print_playlist_summary()
                
            except Exception as e:
                print(f"Error parsing playlist XML: {e}")

    def is_alive(self):
        return self.vlc_instance and self.vlc_instance.process.poll() is None

    def _start_vlc_if_needed(self, path=""):
        if not self.is_alive():
            if not path and self.playlists:
                path = list(self.playlists.values())[0]
            self.vlc_instance = VLCControl(self.cfg, self.user_index, str(path))
            self.music_monitor.vlc_instance = self.vlc_instance
            self.music_monitor.update_status()
            return True
        return False

    def build_playlist_map(self):
        try:
            with os.scandir(self.base_dir_playlist) as entries:
                for entry in entries:
                    self.playlists[Path(entry.name).stem.lower()] = entry.path
        except FileNotFoundError:
            pass

    def _init_album_cache(self):
        for directory in self.smb_base:
            if os.path.exists(directory):
                with os.scandir(directory) as it:
                    for entry in it:
                        if entry.is_dir():
                            self.album_cache.append(entry.path)
        return

    def print_playlist_summary(self):
        duration_str = time.strftime('%H:%M:%S', time.gmtime(self.total_duration_sec))
        
        print("\n" + "="*60)
        print(f"       PLAYLIST CACHE SUMMARY (VLC -> Manager)")
        print("="*60)
        if not self.current_playlist_files:
            print(" /!\\ Cache is EMPTY.")
        else:
            print(f" Items found    : {len(self.current_playlist_files)}")
            print(f" Total Duration : {duration_str}")
            print("-" * 60)
            for i, (name, path) in enumerate(self.current_playlist_files.items()):
                if i < 5:
                    print(f" [{i+1:02d}] {name}")
                else:
                    print(f" ... and {len(self.current_playlist_files) - 5} more.")
                    break
        print("="*60 + "\n")

    def stop(self):
        self.stop_event.set()
        
        if self.auto_switch_thread and self.auto_switch_thread.is_alive():
            self.auto_switch_thread.join(timeout=3)
        
        if self.music_monitor:
            self.music_monitor.stop_timer()
            
        if self.vlc_instance:
            self.vlc_instance.kill_vlc()

    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass
