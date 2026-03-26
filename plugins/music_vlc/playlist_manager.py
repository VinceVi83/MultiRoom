import os
from pathlib import Path

class PlaylistManager:
    """Music VLC Playlist Manager
    
    Role: Manages VLC playlist creation, adding, and removing music tracks.
    
    Methods:
        __init__(self, base_dir_playlist) : Initialize the manager with base directory from config.
        _get_path(self, name) : Clean name and return full file path for playlist.
        create_playlist(self, name) : Create a new empty playlist with standard header.
        add_music(self, name, song_path) : Add a music track to a playlist.
        delete_music(self, name, song_path) : Remove a song from the playlist.
    """
    def __init__(self, base_dir_playlist):
        self.base_dir = base_dir_playlist
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, name):
        safe_name = name.lower().replace(" ", "_")
        return self.base_dir / f"{safe_name}.m3u8"

    def create_playlist(self, name):
        file_path = self._get_path(name.lower())
        if file_path.exists():
            return False
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        
        return True

    def add_music(self, name, song_path):
        file_path = self._get_path(name)
        
        if not file_path.exists():
            self.create_playlist(name)

        song_path_clean = song_path.strip()

        with open(file_path, "r", encoding="utf-8") as f:
            if any(line.strip() == song_path_clean for line in f):
                return False

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{song_path_clean}\n")
        
        return True

    def delete_music(self, name, song_path):
        file_path = self._get_path(name)
        if not file_path.exists(): 
            return False

        song_path_clean = song_path.strip()
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = [l for l in lines if l.strip() != song_path_clean]

        if len(lines) == len(new_lines):
            return False

        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
