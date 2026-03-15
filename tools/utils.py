import time
import os
import shutil
from pathlib import Path
from config_loader import cfg


class FileUtils:
    """Utility class for file operations.

    Summary:
        Provides utility functions for managing file paths, ensuring unique filenames to avoid collisions,
        and handling directory creation with proper error handling.

    Methods:
        get_unique_path(dir_path, base_name, extension=".wav") : Generates a unique file path by appending counter suffixes if the file already exists.
    """

    @staticmethod
    def get_unique_path(dir_path, base_name, extension=".wav"):
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
