import os
import logging
import json
import xml.etree.cElementTree as ET
import requests
import mutagen
from config_loader import cfg

os.chdir("/tmp")
logging.basicConfig(filename='vlc_integration.log', level=logging.DEBUG)


class MusicMetadata:
    """Handles extraction and storage of audio file tags.

    Methods:
        __init__(self) : Initializes the metadata handler with empty metadata dictionary.
        _reset_metadata(self) : Clears all stored metadata values.
        update_metadata(self, song_path) : Extracts metadata from an audio file using mutagen.
    """

    def __init__(self):
        self.metadata = {
            k: "" for k in [
                "title", "artist", "genre", "album",
                "comment", "language", "circle", "filename"
            ]
        }

    def _reset_metadata(self):
        self.metadata = {k: "" for k in self.metadata.keys()}

    def update_metadata(self, song_path):
        self._reset_metadata()
        if not song_path or not os.path.exists(song_path):
            return

        try:
            audio = mutagen.File(song_path)
            if audio is None:
                return

            for key, attr in cfg.mutagen_keys.items():
                if key in audio:
                    tags = audio[key]
                    val = tags.text[0] if hasattr(tags, 'text') else str(tags[0])
                    self.metadata[attr] = val
        except Exception as e:
            logging.error(f"Metadata extraction error for {song_path}: {e}")


class Music:
    """Interacts with VLC HTTP API to track current playback.

    Methods:
        __init__(self, index) : Initializes the Music instance with VLC port and URL configuration.
        update_status(self) : Fetches current VLC status and updates metadata from file.
        get_info_json(self) : Returns metadata as a JSON string for network transmission.
    """

    def __init__(self, index):
        self.current_music = ""
        self.current_dir = ""
        self.full_path = ""
        self.time_remaining = 0
        self.port_ctrl = int(cfg.VLC_PORT_START) + index
        self.vlc_url = f"http://127.0.0.1:{self.port_ctrl}/requests/status.xml"
        self.metadata_handler = MusicMetadata()

    def update_status(self):
        try:
            response = requests.get(self.vlc_url, auth=('', cfg.DICO_USERS_LINUX['user']))
            if response.status_code == 200:
                root = ET.fromstring(response.text)

                for info in root.iter('info'):
                    if info.get('name') == 'filename':
                        self.current_music = info.text
                    if info.get('name') == 'path':
                        self.full_path = info.text

                time_node = root.find('time')
                length_node = root.find('length')

                if time_node is not None and length_node is not None:
                    self.time_remaining = int(length_node.text) - int(time_node.text)

                if self.full_path:
                    self.metadata_handler.update_metadata(self.full_path)

        except Exception as e:
            logging.error(f"Error update_status via VLC: {e}")

    def get_info_json(self):
        if not self.current_music:
            return str(cfg.cfg.RETURN_CODE.ERR)

        data = self.metadata_handler.metadata.copy()
        if not data.get("artist"):
            data["artist"] = self.current_music
        if not data.get("title"):
            data["title"] = self.current_music

        return "metadata:" + json.dumps(data)
