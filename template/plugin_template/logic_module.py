# logic_module.py
import json
from pathlib import Path
from config_loader import cfg

class PluginLogic:
    """Plugin Logic Module
    
    Role: Singleton plugin logic handler for action execution.
    
    Methods:
        __new__(cls) : Implement singleton pattern.
        __init__(self) : Initialize plugin instance.
        perform_action(self, data=None) : Execute plugin actions.
    """
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
        self.data_path = Path(cfg.plugin.DATA_DIR) / "data.json"

    def perform_action(self, data=None):
        return "Result of action"
