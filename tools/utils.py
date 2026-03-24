import time
import os
import shutil
import json
from pathlib import Path
from config_loader import cfg

class Utils:
    """Utility class for file operations
    
    Role: Provides utility functions for managing file paths, ensuring unique filenames to avoid collisions, and handling directory creation with proper error handling.
    
    Methods:
        get_unique_path(dir_path, base_name, extension=".wav") : Generates a unique file path by appending counter suffixes if the file already exists.
        format_result(result) : Format the playlist result from LLM response.
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

    @staticmethod
    def format_result(result):
        if isinstance(result, dict):
            return ",".join([f"{k}:{v}" for k, v in result.items()])
        return str(result)


class SimpleStore:
    """Simple file-based key-value store
    
    Role: Manages simple JSON file storage with load/save operations and default structure handling.
    
    Methods:
        __init__(self, file_path, default_structure=None) : Initialize the store with a file path and optional default structure.
        load(self) : Load data from the file or use default if file doesn't exist.
        save(self) : Save current data to the file.
        get(self, key) : Get value by key.
        update_and_save(self, key, value) : Update a key and save to file.
        delete(self) : Reset data to default structure.
    """

    def __init__(self, file_path, default_structure=None):
        self.file_path = Path(file_path)
        self.default = default_structure if default_structure is not None else {"items": []}
        self.data = {}
        self.load()

    def load(self):
        if not self.file_path.exists():
            self.data = self.default.copy()
            return self.data
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            self.data = content if isinstance(content, type(self.default)) else self.default.copy()
        except Exception:
            self.data = self.default.copy()
        return self.data

    def save(self):
        os.makedirs(self.file_path.parent, exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get(self, key):
        self.load() 
        if isinstance(self.data, dict):
            return self.data.get(key, [])
        return self.data

    def update_and_save(self, key, value):
        if isinstance(self.data, dict):
            self.data[key] = value
            self.save()

    def delete(self):
        self.data = self.default.copy() 
        self.save() 
        return cfg.RETURN_CODE.SUCCESS
