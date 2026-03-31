import shutil
import yaml
import os
import socket
import json
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
from types import SimpleNamespace

class ReturnCode(Enum):
    SUCCESS = 1
    ERR = 2
    ERR_NOT_CONNECTED = 3
    ERR_NOT_IMPLEMENTED = 4
    SUCCESS_NOTHING_TO_DO = 5
    ERR_UNKNOWN_DEVICE = 6
    ERR_INVALID_ARGUMENT = 7
    ERR_NOT_CONFIGURED = 8
    ERR_MISSING_FILE = 9
    SUCCESS_NONSENSE = 10
    NULL = 11
    DUPLICATE = 12

class PluginConfig(SimpleNamespace):
    def __repr__(self):
        
        def custom_format(obj, indent_level=0):
            spacing = "  " * indent_level
            inner_spacing = "  " * (indent_level + 1)
            
            if isinstance(obj, (SimpleNamespace, PluginConfig)):
                items = vars(obj).items()
                if not items: return "{}"
                
                lines = ["{"]
                for k, v in items:
                    formatted_v = custom_format(v, indent_level + 1)
                    lines.append(f'{inner_spacing}"{k}": {formatted_v},')
                # Retrait de la dernière virgule et fermeture
                lines[-1] = lines[-1].rstrip(',')
                lines.append(f"{spacing}")
                return "\n".join(lines)
            
            elif isinstance(obj, str):
                if "\n" in obj:
                    # Pour les prompts, on garde les sauts de ligne réels 
                    # mais on indente chaque ligne pour rester aligné
                    lines = obj.splitlines()
                    indented_lines = [f"\n{inner_spacing}  " + l for l in lines]
                    content = "".join(indented_lines)
                    return f'"""{content}\n{inner_spacing}"""'
                return f'"{obj}"'
            
            elif isinstance(obj, Path):
                return f'"{str(obj)}"'
            
            elif isinstance(obj, list):
                if not obj: return "[]"
                return json.dumps(obj, ensure_ascii=False)
            
            return json.dumps(obj, ensure_ascii=False)

        return custom_format(self)

    def to_dict(self):
        """Retourne le format exact attendu par l'API Ollama."""
        return {
            "model": getattr(self, 'model', cfg.sys.config.MODEL_NAME_MAIN),
            "format": "json" if getattr(self, 'use_json', False) else "",
            "options": vars(self.options) if hasattr(self, 'options') else {},
            "messages": [
                {'role': 'system', 'content': getattr(self, 'prompt', "")}
            ]
        }

class AlisuConfig:
    """Alisu configuration manager class.
    
    Role: Manages plugin configurations, environment variables, and YAML.
    
    Methods:
        __init__(self) : Initialize the configuration object.
        _setup_system_info(self) : Setup system information including IP address.
        _generate_plugin_description_list(self) : Generate plugin description list.
        _sync_and_freeze_plugins(self) : Create folders and copy .env templates.
        _load_env_only(self) : Load environment variables into config objects.
        _load_all_yaml(self) : Load all YAML configurations.
        _process_yaml_config(self, yaml_path, parent_obj) : Process a YAML configuration file.
        _apply_logic_to_agents(self, obj, replacements) : Apply replacement logic to agent prompts.
        _dict_to_namespace(self, data) : Recursively convert dict to SimpleNamespace.
        _parse_to_obj(self, path, obj) : Parse .env file into the provided object.
    """
    def __init__(self):
        self.ROOT = Path(__file__).resolve().parent
        self.DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
        self.plugins_ROOT = self.DATA_DIR / "plugins"
        self.replacements = {}
        self.descriptions = []
        self.cfg = PluginConfig()
        self.cfg.DATA_DIR = self.DATA_DIR
        self.cfg.root = self.ROOT
        self.cfg.LOADED_PLUGINS = []
        self.cfg.RETURN_CODE = ReturnCode

        self._sync_and_freeze_plugins()
        self._load_env_only()
        print("HELLO")
        self._generate_plugin_description_list()
        print("HELLO")
        self._load_all_yaml()
        self._setup_system_info()

    def _setup_system_info(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            self.cfg.sys.INTERFACE_IP = s.getsockname()[0]
        except:
            self.cfg.sys.INTERFACE_IP = "127.0.0.1"
        finally:
            s.close()
        self.cfg.RETURN_CODE = ReturnCode

    def _generate_plugin_description_list(self):
        all_lines = ""
        for description in self.descriptions:
            all_lines += f"{description}\n"
        
        all_lines +="NONE: Nonsense, philosophy, or no clear action"
        self.replacements["REPLACE_PLUGINS"] = all_lines
        return

    def _dict_to_namespace(self, data):
        if isinstance(data, dict):
            return PluginConfig(**{k: self._dict_to_namespace(v) for k, v in data.items()})
        elif isinstance(data, list):
            return [self._dict_to_namespace(i) for i in data]
        return data

    def _parse_to_obj(self, path, obj):
        if not path.exists():
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        for l0_key, l1_data in data.items():
            if not isinstance(l1_data, dict):
                setattr(obj, l0_key, l1_data)
                continue

            for l1_key, l2_data in l1_data.items():
                if l1_key.startswith("config"):
                    obj.has_config_flag = True
                    if isinstance(l2_data, dict) and "DESCRIPTION" in l2_data:
                        self.descriptions.append(f"{l0_key.upper()}: {l2_data['DESCRIPTION']}")

                if isinstance(l2_data, dict):
                    for key, value in l2_data.items():
                        if "replace" in key.lower():
                            self.replacements[key.upper()] = value

            setattr(obj, l0_key, self._dict_to_namespace(l1_data))

    def _sync_and_freeze_plugins(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.plugins_ROOT.mkdir(parents=True, exist_ok=True)
        setattr(self.cfg, "sys", PluginConfig())

        source_plugins = self.ROOT / "plugins"
        if not source_plugins.exists():
            return

        folders = sorted([p for p in source_plugins.iterdir() if p.is_dir() and not p.name.startswith("__")])

        for folder in folders:
            name = folder.name
            self.cfg.LOADED_PLUGINS.append(name)
            target_plugin_dir = self.plugins_ROOT / name
            target_plugin_dir.mkdir(parents=True, exist_ok=True)
            template_file = folder / "config_example.yaml"
            target_file = target_plugin_dir / "config.yaml"

            plugin_obj = PluginConfig()
            plugin_obj.DATA_DIR = target_plugin_dir
            setattr(self.cfg, name, plugin_obj)

            if template_file.exists() and not target_file.exists():
                shutil.copy(template_file, target_file)

    def _load_env_only(self):
        global_config = self.DATA_DIR / "config.yaml"
        if not global_config.exists():
            shutil.copy("config_example.yaml", global_config)
            print(f'SYSTEM : Please copy update configfile in {self.DATA_DIR}')
        
        self._parse_to_obj(global_config, self.cfg)
        
        for name in self.cfg.LOADED_PLUGINS:
            config_path = self.plugins_ROOT / name / "config.yaml"
            if config_path.exists():
                self._parse_to_obj(config_path, getattr(self.cfg, name))
            else:
                print(f'SYSTEM : Please copy update configfile in {config_path}')

    def _load_all_yaml(self):
        self._process_yaml_config(self.ROOT / "agents_config.yaml", self.cfg)
        
        for name in self.cfg.LOADED_PLUGINS:
            yaml_path = self.ROOT / "plugins" / name / "agents_config.yaml"
            self._process_yaml_config(yaml_path, self.cfg)

    def _process_yaml_config(self, yaml_path, parent_obj):
        if not yaml_path.exists():
            return

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            
            for key, value in data.items():
                ns_value = self._dict_to_namespace(value)
                setattr(parent_obj, key, ns_value)
            
            self._apply_logic_to_agents(ns_value)

    def _apply_logic_to_agents(self, obj):
        if hasattr(obj, 'prompt') and isinstance(obj.prompt, str):
            for r_key, r_val in self.replacements.items():
                if r_key in obj.prompt:
                    val_str = ", ".join(map(str, r_val)) if isinstance(r_val, list) else str(r_val)
                    obj.prompt = obj.prompt.replace(r_key, val_str)
            return

        if isinstance(obj, (SimpleNamespace, PluginConfig)):
            for k in vars(obj):
                self._apply_logic_to_agents(getattr(obj, k))
        elif isinstance(obj, list):
            for item in obj:
                self._apply_logic_to_agents(item)

cfg = AlisuConfig().cfg
# print(cfg.sys)
# print(cfg.sys.config.WHISPER)
print(cfg.ALL_PURPOSE.ROUTER_AGENT)
# print(cfg.music_vlc)