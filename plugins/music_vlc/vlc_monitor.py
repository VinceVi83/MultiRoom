import os
import time
import threading
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
import html
import mutagen
import logging
logger = logging.getLogger(__name__)

@dataclass
class MusicInfo:
    """Data class to hold music metadata information.
    
    Role: Stores extracted metadata from audio files.
    
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
    """Music Metadata Extractor
    
    Role: Extracts and manages metadata from audio files using mutagen.
    
    Methods:
        __init__(self) : Initialize metadata extractor with default MusicInfo.
        _get_metadata_value(self, audio, tag) : Get metadata value from audio tags.
        update_metadata(self, song_path) : Update metadata from a song file path.
        _print_metadata_field(self, field_name, value, default_value) : Print a metadata field.
        print_status(self) : Print current metadata status to logger.
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
        logger.info("="*50 + "\n")
        self._print_metadata_field("TITLE", m.title, "Unknown")
        self._print_metadata_field("ARTIST", m.artist, "Unknown")
        self._print_metadata_field("ALBUM", m.album, "Unknown")
        self._print_metadata_field("GENRE", m.genre, "Unknown")
        self._print_metadata_field("CIRCLE/ORG", m.circle, "N/A")
        self._print_metadata_field("LANGUAGE", m.language, "N/A")
        self._print_metadata_field("COMMENT", m.comment, "")
        logger.info("="*50 + "\n")

class VLCMonitor:
    """VLC Media Player Monitor
    
    Role: Monitors VLC media player state, tracks current track, playlist, and provides status updates.
    
    Methods:
        __init__(self, manager) : Initialize monitor with manager instance.
        start(self) : Start the monitoring thread.
        stop(self) : Stop the monitoring thread.
        trigger_update(self) : Trigger a manual update.
        _monitor_loop(self) : Main monitoring loop.
        format_vlc_title(self, title) : Format VLC title string.
        update_track_info(self, base_delay=4) : Update track information from VLC.
        _sync_playlist_data(self) : Sync playlist data from VLC.
        get_playlist_remaining_time(self) : Get remaining time for playlist.
        _is_last_track(self) : Check if current track is last in playlist.
        print_current_track(self) : Print current track status.
        print_playlist_summary(self) : Print playlist summary.
    """
    def __init__(self, manager):
        self.manager = manager
        self.cfg = manager.cfg
        
        self.current_track = ""
        self.full_path = ""
        self.time_remaining = 0
        self.playlist_cache = {}
        self.total_duration = 0
        self.vlc_state = "unknown"
        
        self.stop_event = threading.Event()
        self.monitor_thread = None
        self._lock = threading.Lock()
        self.inactivity = 0

    def start(self):
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        self.stop_event.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def trigger_update(self):
        self.stop_event.set()
        self.stop_event.clear()

    def _monitor_loop(self):
        last_track = ""
        last_playlist_snapshot = []

        while not self.stop_event.is_set():
            self.update_track_info(base_delay=4)
            if self.vlc_state == "stopped":
                self.manager.play_random_album()
                break

            if self.vlc_state == "paused":
                self.inactivity += 1
                if self.inactivity > 6:
                    self.manager.vlc_instance.empty_current_playlist()
                    logger.warning(f"[Monitor] Inactivity timeout ({self.inactivity * 10}min). Clearing playlist.")
                    self.vlc_monitor.stop_event.set()
                    break
                self.stop_event.wait(timeout=600)
                continue

            self.inactivity = 0
            if not self.playlist_cache or self.current_track not in self.playlist_cache:
                self._sync_playlist_data()
                with self._lock:
                    self.full_path = self.playlist_cache.get(self.current_track, "")

            if self.current_track != last_track:
                self.print_current_track()
                last_track = self.current_track

            current_snapshot = list(self.playlist_cache.keys())
            if current_snapshot != last_playlist_snapshot:
                self.print_playlist_summary()
                last_playlist_snapshot = current_snapshot

            sleep_duration = max(1, self.time_remaining+10)
            remaining_str = time.strftime('%H:%M:%S', time.gmtime(sleep_duration))
            logger.info(f"[Monitor] Sleeping for {remaining_str}s")
            self.stop_event.wait(timeout=sleep_duration)

    def format_vlc_title(self, title):
        if not title:
            return ""
        title = html.unescape(title)
        title = title.strip()
        return title
    
    def update_track_info(self, base_delay=4):
        if not self.manager.vlc_instance:
            return False

        retry_count = 0
        current_delay = base_delay
        while retry_count < 5 and not self.stop_event.is_set():
            try:
                time.sleep(2)
                status_xml = self.manager.vlc_instance._vlc_request("status.xml")
                if status_xml:
                    root = ET.fromstring(status_xml)
                    new_track_name = ""
                    self.full_path = ""
                    for info in root.findall(".//category[@name='meta']/info"):
                        if info.get('name') in ['filename', 'title']:
                            potential_name = self.format_vlc_title(info.text)
                            track_data = self.playlist_cache.get(potential_name)
                            if not track_data:
                                stem_name = Path(potential_name).stem
                                track_data = self.playlist_cache.get(stem_name)
                            
                            if isinstance(track_data, dict):
                                new_track_name = potential_name
                                self.full_path = track_data.get("path", "")
                                break
                            else:
                                new_track_name = potential_name

                    if new_track_name:
                        state_node = root.find('state')
                        self.vlc_state = state_node.text if state_node is not None else "unknown"
                        t_node = root.find('time')
                        l_node = root.find('length')
                        with self._lock:
                            self.current_track = new_track_name
                            if t_node is not None and l_node is not None:
                                self.time_remaining = int(l_node.text) - int(t_node.text)
                        return True
                    else:
                        state_node = root.find('state')
                        plid_node = root.find('currentplid')
                        if state_node is not None and state_node.text == "stopped":
                            if plid_node is not None and plid_node.text == "-1":
                                self.vlc_state = "stopped"
                                return False
                
                retry_count += 1
                self.stop_event.wait(timeout=current_delay)
                current_delay *= 2

            except Exception as e:
                logger.error(f"[Monitor] Request error in update_track_info: {e}")
                retry_count += 1
                self.stop_event.wait(timeout=current_delay)
                
        return False

    def _sync_playlist_data(self):
        try:
            xml_data = self.manager.vlc_instance._vlc_request("playlist.xml")
            if not xml_data:
                return

            new_cache = {}
            total_sec = 0
            root = ET.fromstring(xml_data)
            for leaf in root.iter('leaf'):
                name = leaf.get('name')
                uri = leaf.get('uri')
                duration = leaf.get('duration')
                if name and uri:
                    clean_path = urllib.parse.unquote(uri.replace("file://", ""))
                    d = int(duration) if (duration and duration.isdigit()) else 0
                    new_cache[name] = {
                        "path": clean_path,
                        "duration": d
                    }
                    total_sec += d
                    
            with self._lock:
                self.playlist_cache = new_cache
                self.total_duration = total_sec
            
        except Exception as e:
            logger.error(f"[Monitor] Playlist sync error: {e}")

    def get_playlist_remaining_time(self):
        self.update_track_info()
        with self._lock:
            if not self.playlist_cache or not self.current_track:
                return 0
            
            total_remaining = 0
            found_current = False
            curr = self.current_track.strip().lower()
            curr_stem = Path(curr).stem

            for name, info in self.playlist_cache.items():
                name_clean = name.strip().lower()
                
                if not found_current and (name_clean == curr or name_clean == curr_stem or curr in name_clean):
                    found_current = True
                    total_remaining += self.time_remaining
                    continue
                
                if found_current:
                    total_remaining += info.get("duration", 0)
            
            return total_remaining

    def _is_last_track(self):
        if not self.playlist_cache or not self.current_track:
            return False
        
        track_list = list(self.playlist_cache.keys())
        return track_list[-1] == self.current_track

    def print_current_track(self):
        remaining_str = time.strftime('%H:%M:%S', time.gmtime(self.time_remaining))
        logger.info("=" * 50)
        logger.info("[CURRENT TRACK]")
        logger.info(f"   VLC status : {self.vlc_state}")
        logger.info(f"   Name       : {self.current_track}")
        logger.info(f"   Remaining  : {remaining_str}s")
        logger.info(f"   Path       : {self.full_path}")
        logger.info("=" * 50 + "\n")

    def print_playlist_summary(self):
        total_str = time.strftime('%H:%M:%S', time.gmtime(self.total_duration))
        remaining_sec = self.get_playlist_remaining_time()
        remaining_str = time.strftime('%H:%M:%S', time.gmtime(remaining_sec))
        logger.info("=" * 50)
        logger.info(f"[CURRENT PLAYLIST]")
        logger.info(f"   VLC status        : {self.vlc_state}")
        logger.info(f"   Name              : {self.manager.current_album_name}")
        logger.info(f"   Total Duration    : {total_str}")
        logger.info(f"   Remaining to Play : {remaining_str}")
        logger.info(f"   Total Tracks      : {len(self.playlist_cache)}")
        logger.info("-" * 50)
        tracks = list(self.playlist_cache.keys())
        for i, t in enumerate(tracks):
            mark = " > " if t == self.current_track else "   "
            logger.info(f"{mark}[{i+1:02d}] {t}")
        logger.info("=" * 50 + "\n")
