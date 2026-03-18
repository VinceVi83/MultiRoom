# logic_module.py
import json
from pathlib import Path
from config_loader import cfg

class PluginLogic:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PluginLogic, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # Setup paths or connections here
        # self.data_path = Path(cfg.plugin.DATA_DIR) / "data.json"

    def perform_action(self, data=None):
        # Implementation logic here
        return "Result of action"