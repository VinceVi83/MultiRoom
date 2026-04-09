import logging
logger = logging.getLogger(__name__)

class PlaylistManager:
    """Music Playlist Manager
    
    Role: Manages VLC playlist creation, song addition, and deletion.
    
    Methods:
        __init__(self, base_dir_playlist) : Initialize playlist manager with base directory.
        _get_path(self, name) : Get safe file path for playlist.
        create_playlist(self, name) : Create a new empty playlist file.
        add_music(self, name, song_path) : Add a song to an existing playlist.
        delete_music(self, name, song_path) : Remove a song from a playlist.
    """
    def __init__(self, base_dir_playlist):
        if base_dir_playlist is None:
            raise ValueError("base_dir_playlist cannot be None")
        self.base_dir = base_dir_playlist
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, name):
        safe_name = name.lower().replace(" ", "_")
        return self.base_dir / f"{safe_name}.m3u8"

    def _write_header(self, file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
        return True

    def _read_lines(self, file_path):
        if not file_path.exists():
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            return f.readlines()

    def _write_lines(self, file_path, lines):
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def _append_line(self, file_path, line):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{line}\n")

    def create_playlist(self, name):
        file_path = self._get_path(name.lower())
        if file_path.exists():
            return False
        
        self._write_header(file_path)
        
        return True

    def add_music(self, name, song_path):
        file_path = self._get_path(name)
        
        if not file_path.exists():
            self.create_playlist(name)

        song_path_clean = song_path.strip()

        lines = self._read_lines(file_path)
        
        if any(line.strip() == song_path_clean for line in lines):
            return False

        self._append_line(file_path, song_path_clean)
        
        return True

    def delete_music(self, name, song_path):
        file_path = self._get_path(name)
        if not file_path.exists(): 
            return False

        song_path_clean = song_path.strip()
        
        lines = self._read_lines(file_path)
        new_lines = [l for l in lines if l.strip() != song_path_clean]

        if len(lines) == len(new_lines):
            return False

        self._write_lines(file_path, new_lines)
        return True
