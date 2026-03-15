import time
import os
import shutil
from pathlib import Path
from config_loader import cfg


class FileUtils:
    @staticmethod
    def get_unique_path(dir_path, base_name, extension=".wav"):
        """Generate a unique path by avoiding collisions."""
        directory = Path(dir_path)
        directory.mkdir(parents=True, exist_ok=True)

        filename = f"{base_name}{extension}"
        dest_path = directory / filename

        counter = 1
        while dest_path.exists():
            filename = f"{base_name}_{counter}{extension}"
            dest_path = directory / filename
            counter += 1

        return dest_path, filename
