import os
import logging
import xml.etree.cElementTree as ET
import mutagen
import threading
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

@dataclass
class MusicInfo:
    """Music metadata information container
    
    Role: Stores music track metadata fields.
    
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
    """Music metadata extraction and display handler
    
    Role: Extracts metadata from audio files and prints status information.
    
    Methods:
        __init__(self) : Initialize metadata handler with default MusicInfo instance.
        _get_metadata_value(self, audio, tag) : Get metadata value from audio tags.
        update_metadata(self, song_path) : Update metadata from audio file.
        _print_metadata_field(self, field_name, value, default_value) : Print a metadata field.
        print_status(self) : Print all current metadata fields.
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

    def _get_metadata_value(self, audio, tag):
        if tag in audio:
            value = audio[tag]
            if hasattr(value, 'text') and value.text:
                return value.text[0]
            elif isinstance(value, list) and len(value) > 0:
                return str(value[0])
            else:
                return str(value)
        return None

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
                    value = self._get_metadata_value(audio, tag)
                    if value is not None:
                        setattr(self.data, attr, value)
                        break
        except Exception as e:
            logging.error(f"Metadata error: {e}")

    def _print_metadata_field(self, field_name, value, default_value):
        actual_value = value if value else default_value
        logger.info(f"{field_name}          : {actual_value}")

    def print_status(self):
        m = self.data
        self._print_metadata_field("TITLE", m.title, "Unknown")
        self._print_metadata_field("ARTIST", m.artist, "Unknown")
        self._print_metadata_field("ALBUM", m.album, "Unknown")
        self._print_metadata_field("GENRE", m.genre, "Unknown")
        self._print_metadata_field("CIRCLE/ORG", m.circle, "N/A")
        self._print_metadata_field("LANGUAGE", m.language, "N/A")
        self._print_metadata_field("COMMENT", m.comment, "")
        logger.info("="*50 + "\n")

class MusicMonitor:
    """VLC music monitoring and status update service
    
    Role: Monitors VLC instance, extracts music metadata, and schedules periodic updates.
    
    Methods:
        __init__(self, cfg, index, vlc=None) : Initialize monitor with config, index, and VLC instance.
        update_status(self) : Update status from VLC and extract metadata.
        force_update(self) : Force immediate status update.
        _schedule_next_auto_update(self) : Schedule next automatic status update.
        stop_timer(self) : Cancel and stop the update timer.
        print_status(self) : Print monitor status information.
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
                    if info.get('name') == 'title':
                        filename = info.text
                        if filename != self.current_music or self.full_path == "":
                            self.current_music = filename
                            self.full_path = self.playlist_cache.get(filename, "")
                            if self.full_path:
                                self.metadata_handler.update_metadata(self.full_path)
                                self.metadata_handler.print_status()

        except Exception as e:
            self.time_remaining = 0
            logger.error(f"Exception: {type(e).__name__} - {e}")
    
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
        logger.info("-" * 30)
        logger.info(f"PORT VLC       : {self.port_ctrl}")
        logger.info(f"FILE           : {self.current_music}")
        logger.info(f"FULL PATH      : {self.full_path}")
        logger.info(f"TIME REMAINING : {self.time_remaining}s")
        
        m = self.metadata_handler.data
        logger.info(f"METADATA       : {m.title} - {m.artist} ({m.album})")
        logger.info(f"GENRE/CIRCLE   : {m.genre} / {m.circle}")
        logger.info("-" * 30)
