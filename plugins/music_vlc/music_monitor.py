import os
import logging
import xml.etree.cElementTree as ET
import requests
import mutagen
import threading
from dataclasses import dataclass
from config_loader import cfg

@dataclass
class MusicInfo:
    """Music Metadata Class
    
    Role: Stores music file metadata extracted from audio files.
    
    Methods:
        __init__(self, title='', artist='', genre='', album='', comment='', language='', circle='') : Initialize with default empty values.
    """
    title: str = ""
    artist: str = ""
    genre: str = ""
    album: str = ""
    comment: str = ""
    language: str = ""
    circle: str = ""

class MusicMetadata:
    """Music Metadata Handler Class
    
    Role: Extracts and manages metadata from audio files using mutagen.
    
    Methods:
        __init__(self) : Initialize the metadata handler.
        update_metadata(self, song_path) : Update metadata for a given song path.
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
            if not audio: return

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

class MusicMonitor:
    """VLC Music Monitor Class
    
    Role: Monitors VLC media player and tracks music playback status.
    
    Methods:
        __init__(self, index) : Initialize the monitor with VLC port index.
        update_status(self) : Update internal info from VLC.
        force_update(self) : Trigger an update following a manual action.
        _do_update(self) : Perform the actual update operation.
        _schedule_next_auto_update(self) : Schedule next automatic update.
        stop(self) : Stop the monitor and cancel any pending updates.
    """
    def __init__(self, index):
        self.index = index
        self.current_music = ""
        self.full_path = ""
        self.time_remaining = 0
        self.port_ctrl = int(cfg.music_vlc.VLC_PORT_START) + index
        self.vlc_url = f"http://127.0.0.1:{self.port_ctrl}/requests/status.xml"
        self.metadata_handler = MusicMetadata()
        self.timer_update = None

    def update_status(self):
        try:
            response = requests.get(self.vlc_url, auth=('', cfg.music_vlc.DICO_USERS_LINUX['user']), timeout=2)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                
                new_path = ""
                for info in root.iter('info'):
                    if info.get('name') == 'path': 
                        new_path = info.text
                    if info.get('name') == 'filename': 
                        self.current_music = info.text

                self.metadata_handler.update_metadata(new_path)
                self.full_path = new_path 
                t_node = root.find('time')
                l_node = root.find('length')
                self.time_remaining = int(l_node.text) - int(t_node.text) if t_node is not None else 0
        except Exception:
            pass

    def force_update(self):
        if self.timer_update:
            self.timer_update.cancel()
        self.timer_update = threading.Timer(1.5, self._do_update)
        self.timer_update.daemon = True
        self.timer_update.start()

    def _do_update(self):
        self.update_status() 
        self._schedule_next_auto_update()

    def _schedule_next_auto_update(self):
        if self.timer_update:
            self.timer_update.cancel()
        if self.time_remaining > 0:
            wait_time = self.time_remaining + 3
            self.timer_update = threading.Timer(wait_time, self._do_update)
            self.timer_update.daemon = True
            self.timer_update.start()

    def stop(self):
        if self.timer_update:
            self.timer_update.cancel()
