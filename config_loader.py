import shutil
import yaml
import os
import socket
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
    """Container for a single plugin's env vars and yaml structure."""
    pass

class AlisuConfig:
    """Alisu configuration manager class.
    
    Role: Manages plugin configurations, environment variables, and YAML payloads.
    
    Methods:
        __init__(self) : Initialize the configuration object.
        _setup_system_info(self) : Setup system information including IP address.
        _generate_plugin_description_list(self) : Generate plugin description list.
        _sync_and_freeze_plugins(self) : Create folders and copy .env templates.
        _load_env_only(self) : Load environment variables into config objects.
        _load_all_yaml_and_payloads(self) : Load all YAML configurations and payloads.
        _process_yaml_config(self, yaml_path, parent_obj) : Process a YAML configuration file.
        _apply_logic_to_agents(self, obj, replacements) : Apply replacement logic to agent prompts.
        _dict_to_namespace(self, data) : Recursively convert dict to SimpleNamespace.
        _parse_to_obj(self, path, obj) : Parse .env file into the provided object.
    """
    def __init__(self):
        self.ROOT = Path(__file__).resolve().parent
        self.DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
        self.plugins_ROOT = self.DATA_DIR / "plugins"
        
        self.cfg = SimpleNamespace()
        self.cfg.DATA_DIR = self.DATA_DIR
        self.cfg.root = self.ROOT
        self.cfg.LOADED_PLUGINS = []
        self.cfg.RETURN_CODE = ReturnCode

        self._sync_and_freeze_plugins()
        self._load_env_only()
        self._generate_plugin_description_list()

        self._load_all_yaml_and_payloads()
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
        for i, name in enumerate(self.cfg.LOADED_PLUGINS, start=1):
            plugin_obj = getattr(self.cfg, name)
            
            description = getattr(plugin_obj, "DESCRIPTION", "No description provided")

            all_lines += f"{i}: {name.upper()} ({description})\n"
        
        all_lines +="0: NONE (Nonsense, philosophy, or no clear action)"
        return all_lines

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
            template_file = folder / ".env_template"
            target_env = target_plugin_dir / ".env"

            plugin_obj = PluginConfig()
            plugin_obj.DATA_DIR = target_plugin_dir
            setattr(self.cfg, name, plugin_obj)

            if template_file.exists() and not target_env.exists():
                shutil.copy(template_file, target_env)

    def _load_env_only(self):
        global_env = self.DATA_DIR / ".env"
        if global_env.exists():
            self._parse_to_obj(global_env, self.cfg.sys)
        
        for name in self.cfg.LOADED_PLUGINS:
            env_path = self.plugins_ROOT / name / ".env"
            if env_path.exists():
                self._parse_to_obj(env_path, getattr(self.cfg, name))

    def _generate_plugin_description_list(self):
        all_lines = ""
        for i, name in enumerate(self.cfg.LOADED_PLUGINS, start=1):
            plugin_obj = getattr(self.cfg, name)
            description = getattr(plugin_obj, "DESCRIPTION", "No description provided")
            all_lines += f"{i}: {name.upper()} ({description})\n"
        
        all_lines += "0: NONE (Nonsense, philosophy, or no clear action)"
        
        self.cfg.sys.REPLACE_PLUGINS = all_lines

    def _load_all_yaml_and_payloads(self):
        self._process_yaml_config(self.ROOT / "agents_config.yaml", self.cfg.sys)
        
        for name in self.cfg.LOADED_PLUGINS:
            yaml_path = self.ROOT / "plugins" / name / "agents_config.yaml"
            self._process_yaml_config(yaml_path, getattr(self.cfg, name))

    def _process_yaml_config(self, yaml_path, parent_obj):
        if not yaml_path.exists():
            return

        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            
            replacements = {k: v for k, v in vars(parent_obj).items() if k.startswith("REPLACE_")}

            for key, value in data.items():
                ns_value = self._dict_to_namespace(value)
                setattr(parent_obj, key, ns_value)
                
                self._apply_logic_to_agents(ns_value, replacements)

    def _apply_logic_to_agents(self, obj, replacements):
        if hasattr(obj, 'prompt') and isinstance(obj.prompt, str):
            for r_key, r_val in replacements.items():
                if r_val:
                    obj.prompt = obj.prompt.replace(r_key, str(r_val))
            
            self._create_payload(obj)
            return

        if isinstance(obj, SimpleNamespace):
            for k in vars(obj):
                self._apply_logic_to_agents(getattr(obj, k), replacements)

    def _dict_to_namespace(self, data):
        if isinstance(data, dict):
            return SimpleNamespace(**{k: self._dict_to_namespace(v) for k, v in data.items()})
        elif isinstance(data, list):
            return [self._dict_to_namespace(i) for i in data]
        return data

    def _parse_to_obj(self, path, obj):
        values = dotenv_values(path)
        for k, v in values.items():
            if not v:
                continue
            
            val = v
            if k in "DESCRIPTION" or k.startswith("LINK_"):
                val = v
            elif k.startswith("LIST") or k == "AGENT_FEATURES":
                val = [i.strip() for i in v.split(',')]
            elif k.startswith("DICO"):
                val = {i.split(':')[0].strip(): i.split(':')[1].strip() for i in v.split(',') if ':' in i}
            
            setattr(obj, k, val)

    def _create_payload(self, agent):
        agent._payload = {
            "model": getattr(agent, 'model', self.cfg.sys.MODEL_NAME_MAIN),
            "format": "json" if getattr(agent, 'use_json', False) else "",
            "options": vars(agent.options) if hasattr(agent, 'options') else {},
            "messages": [
                {'role': 'system', 'content': agent.prompt}
            ]
        }

cfg = AlisuConfig().cfg
