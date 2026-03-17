import shutil
import yaml
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
from types import SimpleNamespace


class AlisuConfig:
    """Container for plugin configuration management.
    
    Methods
    -----
    __init__(self) : Initialize the AlisuConfig instance with paths and load configs.
    _sync_and_freeze_plugins(self) : Create necessary directories and copy plugin templates.
    _load_global_configs(self) : Load global .env and config.yaml files into self.cfg.
    _load_all_plugins(self) : Load individual plugin configurations from .env and yaml files.
    _dict_to_namespace(self, data) : Recursively convert dict to SimpleNamespace for dot notation.
    _parse_to_obj(self, path, obj) : Parse .env variables into a specific object.
    """

    def __init__(self):
        self.ROOT = Path(__file__).resolve().parent
        self.DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
        self.plugins_ROOT = self.DATA_DIR / "plugins"
        
        self.cfg = SimpleNamespace()
        self.cfg.DATA_DIR = self.DATA_DIR
        self.cfg.LOADED_PLUGINS = []
        
        self._sync_and_freeze_plugins()
        
        self._load_global_configs()
        
        self._load_all_plugins()

    def _sync_and_freeze_plugins(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.plugins_ROOT.mkdir(parents=True, exist_ok=True)
        
        source_plugins = self.ROOT / "plugins"
        if not source_plugins.exists():
            return

        plugin_folders = sorted([p for p in source_plugins.iterdir() if p.is_dir() and not p.name.startswith("__")])

        for folder in plugin_folders:
            name = folder.name
            self.cfg.LOADED_PLUGINS.append(name)
            
            setattr(self.cfg, name, SimpleNamespace())
            
            target_dir = self.plugins_ROOT / name
            target_dir.mkdir(parents=True, exist_ok=True)
            
            template = folder / ".env_template"
            target_env = target_dir / ".env"
            if template.exists() and not target_env.exists():
                shutil.copy(template, target_env)

    def _load_global_configs(self):
        global_env = self.DATA_DIR / ".env"
        if global_env.exists():
            self._parse_to_obj(global_env, self.cfg)

        global_yaml = self.DATA_DIR / "config.yaml"
        if global_yaml.exists():
            with open(global_yaml, 'r', encoding='utf-8') as f:
                self.cfg.GLOBAL = self._dict_to_namespace(yaml.safe_load(f) or {})

    def _load_all_plugins(self):
        for name in self.cfg.LOADED_PLUGINS:
            plugin_obj = getattr(self.cfg, name)
            
            env_path = self.plugins_ROOT / name / ".env"
            if env_path.exists():
                self._parse_to_obj(env_path, plugin_obj)

            yaml_path = self.ROOT / "plugins" / name / "config.yaml"
            if yaml_path.exists():
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
                    for key, value in data.items():
                        setattr(plugin_obj, key, self._dict_to_namespace(value))

    def _dict_to_namespace(self, data):
        """Recursively converts dict to SimpleNamespace for dot notation."""
        if isinstance(data, dict):
            return SimpleNamespace(**{k: self._dict_to_namespace(v) for k, v in data.items()})
        elif isinstance(data, list):
            return [self._dict_to_namespace(i) for i in data]
        return data

    def _parse_to_obj(self, path, obj):
        """Helper to parse .env variables into a specific object."""
        values = dotenv_values(path)
        for k, v in values.items():
            if v:
                key = k.upper().strip()
                val = v.strip()
                if ',' in val and not (val.startswith('{') or val.startswith('[')):
                    val = [i.strip() for i in val.split(',')]
                setattr(obj, key, val)


cfg = AlisuConfig().cfg
