import os
import logging
import xml.etree.cElementTree as ET
import requests
import mutagen
import threading
from dataclasses import dataclass
import subprocess
from pathlib import Path
from plugins.music_vlc.vlc_control import VLCControl

@dataclass
class MusicInfo:
    """Music metadata information container
    
    Role: Stores song metadata extracted from audio files.
    
    Fields:
        title: Song title.
        artist: Artist name.
        genre: Music genre.
        album: Album name.
        comment: Additional comment.
        language: Audio language.
        circle: Organization/circle name.
    """
    title: str = ""
    artist: str = ""
    genre: str = ""
    album: str = ""
    comment: str = ""
    language: str = ""
    circle: str = ""

class MusicMetadata:
    """Music metadata handler for VLC audio files
    
    Role: Extracts and manages metadata from audio files using mutagen.
    
    Methods:
        __init__(self) : Initialize metadata handler.
        update_metadata(self, song_path) : Update metadata from audio file.
        print_status(self) : Print current playback status.
    """
    METADATA_MAP = {
        "title": ["TIT2", "title", "nam"],
        "artist": ["TPE1", "artist", "ART"],
        "album": ["TALB", "album", "alb"],
        "genre": ["TCON", "genre", "gnr"],
        "language": ["TLAN", "language"],
        "comment": ["COMM", "description", "comment"],
        "circle": ["TXXX:CIRCLE", "organization", "cprt"]
    }

    def __init__(self):
        self.data = MusicInfo()
        self._last_path = None

    def update_metadata(self, song_path):
        if not song_path or song_path == self._last_path:
            return
        
        self.data = MusicInfo()
        self._last_path = song_path
        
        local_path = song_path.replace("file://", "") if song_path.startswith("file://") else song_path

        if not os.path.exists(local_path):
            return

        try:
            audio = mutagen.File(local_path)
            if not audio:
                return

            for attr, tags in self.METADATA_MAP.items():
                for tag in tags:
                    if tag in audio:
                        value = audio[tag]
                        if hasattr(value, 'text') and value.text:
                            final_val = value.text[0]
                        elif isinstance(value, list) and len(value) > 0:
                            final_val = str(value[0])
                        else:
                            final_val = str(value)
                        
                        setattr(self.data, attr, final_val)
                        break
        except Exception as e:
            logging.error(f"Metadata error: {e}")

    def print_status(self):
        m = self.metadata_handler.data
        
        print("\n" + "="*50)
        print("          VLC PLAYBACK STATUS")
        print("="*50)
        print(f"FILE           : {self.current_music}")
        print(f"PATH           : {self.full_path}")
        print(f"TIME REMAINING : {self.time_remaining}s")
        print("-" * 50)
        print("                METADATA")
        print("-" * 50)
        print(f"TITLE          : {m.title if m.title else 'Unknown'}")
        print(f"ARTIST         : {m.artist if m.artist else 'Unknown'}")
        print(f"ALBUM          : {m.album if m.album else 'Unknown'}")
        print(f"GENRE          : {m.genre if m.genre else 'Unknown'}")
        print(f"CIRCLE/ORG     : {m.circle if m.circle else 'N/A'}")
        print(f"LANGUAGE       : {m.language if m.language else 'N/A'}")
        print(f"COMMENT        : {m.comment if m.comment else ''}")
        print("="*50 + "\n")

class MusicMonitor:
    """VLC music playback monitor
    
    Role: Monitors VLC playback status and updates metadata periodically.
    
    Methods:
        __init__(self, cfg, index, vlc=None) : Initialize monitor with config.
        update_status(self) : Update playback status from VLC.
        force_update(self) : Force immediate status update.
        _schedule_next_auto_update(self) : Schedule next automatic update.
        stop_timer(self) : Stop the update timer.
        print_status(self) : Print monitor status summary.
    """
    def __init__(self, cfg, index, vlc=None):
        self.index = index
        self.cfg = cfg
        self.port_ctrl = int(self.cfg.config.VLC_PORT_START) + index
        self.vlc_url = f"http://127.0.0.1:{self.port_ctrl}/requests/status.xml"
        self.current_music = ""
        self.full_path = ""
        self.time_remaining = 0
        
        self.metadata_handler = MusicMetadata()
        self.playlist_cache = {}

        self.vlc_instance = vlc
        self.timer_update = None
        self._is_updating = False
        self._lock = threading.Lock()

    def update_status(self):
        if self._is_updating or not self.vlc_instance:
            return
            
        if not getattr(self.vlc_instance, 'is_initialized', False):
            self._schedule_next_auto_update()
            return
        self._is_updating = True
        self.stop_timer()

        try:
            status_xml = self.vlc_instance._vlc_request("status.xml")
            if status_xml:
                root = ET.fromstring(status_xml)
                
                t_node = root.find('time')
                l_node = root.find('length')
                if t_node is not None and l_node is not None:
                    self.time_remaining = int(l_node.text) - int(t_node.text)
                
                for info in root.findall(".//category[@name='meta']/info"):
                    if info.get('name') == 'filename':
                        filename = info.text
                        if filename != self.current_music:
                            self.current_music = filename
                            self.full_path = self.playlist_cache.get(filename, "")
                            if self.full_path:
                                self.metadata_handler.update_metadata(self.full_path)
                                self.metadata_handler.print_status()

        except Exception as e:
            self.time_remaining = 0
            print(f"Exception: {type(e).__name__} - {e}")
    
        finally:
            self._is_updating = False
            self._schedule_next_auto_update()

    def force_update(self):
        self.update_status()

    def _schedule_next_auto_update(self):
        wait_time = self.time_remaining + 3 if self.time_remaining > 0 else 5
        self.timer_update = threading.Timer(wait_time, self.update_status)
        self.timer_update.daemon = True
        self.timer_update.start()

    def stop_timer(self):
        if self.timer_update:
            self.timer_update.cancel()
            self.timer_update = None

    def print_status(self):
        print("-" * 30)
        print(f"PORT VLC       : {self.port_ctrl}")
        print(f"FILE           : {self.current_music}")
        print(f"FULL PATH      : {self.full_path}")
        print(f"TIME REMAINING : {self.time_remaining}s")
        
        m = self.metadata_handler.data
        print(f"METADATA       : {m.title} - {m.artist} ({m.album})")
        print(f"GENRE/CIRCLE   : {m.genre} / {m.circle}")
        print("-" * 30)
