import os
import json
from pathlib import Path
from config_loader import cfg
import sys
import logging
import threading
import requests
logger = logging.getLogger(__name__)

class LocalFilesFilter(logging.Filter):
    """Local Files Logging Filter
    
    Role: Filters log records to only include local Python files.
    
    Methods:
        __init__(self) : Initialize filter with local files list.
        filter(self, record) : Filter log record based on filename.
    """
    def __init__(self):
        super().__init__()
        self.local_files = set()
        root_dir = Path(__file__).resolve().parent.parent
        for path in root_dir.rglob("*.py"):
            if "__pycache__" in path.parts or any(part.startswith('.') for part in path.parts):
                continue
            self.local_files.add(path.name)

    def filter(self, record):
        return record.filename in self.local_files

def setup_logging():
    log_dir_path = cfg.DATA_DIR / "logs"
    if not os.path.exists(log_dir_path):
        os.makedirs(log_dir_path, exist_ok=True)

    date_format = "%y%m%d:%H:%M:%S"

    class SmartFormatter(logging.Formatter):
        def format(self, record):
            if record.funcName in ['print_current_track', 'print_playlist_summary']:
                msg = record.getMessage()
                try:
                    msg = msg.encode('latin-1').decode('utf-8')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
                return msg
            return super().format(record)

    if cfg.verbose:
        log_format = "[%(asctime)s][%(filename)s][%(funcName)s](%(levelname)s): %(message)s"
    else:
        log_format = "[%(asctime)s][%(funcName)s](%(levelname)s): %(message)s"
    
    formatter = SmartFormatter(fmt=log_format, datefmt=date_format)

    local_filter = LocalFilesFilter()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(local_filter)

    log_file = log_dir_path / "debug.log"
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(local_filter)
    
    root_logger = logging.getLogger()
    if cfg.debug:
        root_logger.setLevel(logging.DEBUG)
    else:
        root_logger.setLevel(logging.INFO)
    
    root_logger.handlers = []
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

class Utils:
    """Utility Functions for File Operations and Data Formatting
    
    Role: Provides helper methods for file path management, data formatting, and type conversion.
    
    Methods:
        get_unique_path(dir_path, base_name, extension='.wav') : Generate unique file path with counter.
        format_result(result) : Format dict or other result as string.
        to_int(data, key) : Convert value to integer or return -1 on error.
        to_str(data, key) : Convert value to string or return 'ERROR' on empty/None.
        enable_bypass() : Return bypass configuration flag.
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
                formatted_items = []
                for k, v in result.items():
                    formatted_items.append(f"{k}:{v}")
                return ",".join(formatted_items)
            except Exception:
                return str(result)
        return str(result)

    @staticmethod
    def to_int(data, key):
        try:
            val = data.get(key)
            if val is not None:
                return int(val)
            return -1
        except (ValueError, TypeError):
            return -1
    
    @staticmethod
    def to_str(data, key):
        val = data.get(key)
        if val is None:
            return "ERROR"
        val_str = str(val)
        if val_str.strip() == "":
            return "ERROR"
        return val_str
        
    @staticmethod
    def enable_bypass():
        return cfg.no_bypass

    @staticmethod
    def send_discord_notification(message, channel=None, files=None):
        if getattr(cfg.sys, 'discord', None) is None:
            logger.info("Discord not configured")
            return

        def post_request():
            try:
                payload = {
                    "channel_name": channel if channel else cfg.sys.discord.CHANNEL,
                    "msg": message,
                    "attachments": files if files else []
                }
                requests.post(f"http://{cfg.sys.discord.HOST}:{cfg.sys.discord.PORT}/send",
                              json=payload,
                              timeout=5)
            except Exception as e:
                pass

        threading.Thread(target=post_request, daemon=True).start()

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
