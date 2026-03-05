import os
import logging
import json
import xml.etree.cElementTree as ET
import requests
import mutagen  # type: ignore
from Gestion import Ctes
from Gestion.Ctes import RETURN_CODE

# Configuration initiale
os.chdir("/tmp")
logging.basicConfig(filename='vlc_integration.log', level=logging.DEBUG)


class MusicMetadata:
    """Handles extraction and storage of audio file tags."""

    def __init__(self):
        self.metadata = {
            k: "" for k in [
                "title", "artist", "genre", "album", 
                "comment", "language", "circle", "filename"
            ]
        }

    def _reset_metadata(self):
        """Clear all stored metadata values."""
        self.metadata = {k: "" for k in self.metadata.keys()}

    def update_metadata(self, song_path):
        """Extract metadata from file using mutagen."""
        self._reset_metadata()
        if not song_path or not os.path.exists(song_path):
            return

        try:
            audio = mutagen.File(song_path)
            if audio is None:
                return

            for key, attr in Ctes.mutagen_keys.items():
                if key in audio:
                    # Extraction sécurisée du contenu texte
                    tags = audio[key]
                    val = tags.text[0] if hasattr(tags, 'text') else str(tags[0])
                    self.metadata[attr] = val
        except Exception as e:
            logging.error(f"Metadata extraction error for {song_path}: {e}")


class Music:
    """Interacts with VLC HTTP API to track current playback."""

    def __init__(self, index):
        self.current_music = ""
        self.current_dir = ""
        self.full_path = ""
        self.time_remaining = 0
        self.port_ctrl = str(9000 + index)
        self.vlc_url = f"http://{Ctes.local_ip}:{self.port_ctrl}/requests/status.xml"
        self.metadata_handler = MusicMetadata()

    def update_status(self):
        """Fetch current VLC status and update metadata."""
        try:
            # Utilisation de pwd_vlc défini dans Ctes
            response = requests.get(self.vlc_url, auth=('', Ctes.cfg.pwd_vlc))
            if response.status_code == 200:
                root = ET.fromstring(response.text)

                for info in root.iter('info'):
                    if info.get('name') == 'filename':
                        self.current_music = info.text
                    if info.get('name') == 'path':
                        self.full_path = info.text

                # Extraction du temps
                time_node = root.find('time')
                length_node = root.find('length')
                
                if time_node is not None and length_node is not None:
                    self.time_remaining = int(length_node.text) - int(time_node.text)

                if self.full_path:
                    self.metadata_handler.update_metadata(self.full_path)

        except Exception as e:
            logging.error(f"Error update_status via VLC: {e}")

    def get_info_json(self):
        """Returns metadata as a JSON string for network transmission."""
        if not self.current_music:
            return str(RETURN_CODE.ERR)

        data = self.metadata_handler.metadata.copy()
        # On s'assure que l'artiste et le titre ne sont pas vides
        if not data.get("artist"):
            data["artist"] = self.current_music
        if not data.get("title"):
            data["title"] = self.current_music

        return "metadata:" + json.dumps(data)