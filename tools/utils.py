import time
import os
import shutil
import json
from pathlib import Path
from config_loader import cfg

class Utils:
    """Utility Functions for File Operations and Data Formatting
    
    Role: Provides helper methods for file path management, data formatting, and type conversion.
    
    Methods:
        get_unique_path(dir_path, base_name, extension='.wav') : Generate unique file path with counter.
        format_result(result) : Format dict or other result as string.
        to_int(data, key) : Convert value to integer or return -1 on error.
        to_str(data, key) : Convert value to string or return 'ERROR' on empty/None.
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
            try:
                return ",".join([f"{k}:{v}" for k, v in result.items()])
            except Exception:
                return str(result)
        return str(result)

    @staticmethod
    def to_int(data, key):
        try:
            val = data.get(key)
            return int(val) if val is not None else -1
        except (ValueError, TypeError):
            return -1
    
    @staticmethod
    def to_str(data, key):
        val = data.get(key)
        if val is None or str(val).strip() == "":
            return "ERROR"
        return str(val)


class SimpleStore:
    """Simple Key-Value Store with JSON Persistence
    
    Role: Manages persistent storage of data structures with load/save operations.
    
    Methods:
        __init__(self, file_path, default_structure=None) : Initialize store with file path and default structure.
        load(self) : Load data from file or use default structure.
        save(self) : Save current data to file.
        get(self, key) : Get value by key.
        update_and_save(self, key, value) : Update key value and persist to file.
        delete(self) : Reset data to default structure.
    """
    def __init__(self, file_path, default_structure=None):
        self.file_path = Path(file_path) if file_path else None
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
