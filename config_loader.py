import shutil
import yaml
import socket
import json
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
import logging
logger = logging.getLogger(__name__)

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
    ERR_FILE_NOT_FOUND = 13

class PluginConfig(SimpleNamespace):
    def __repr__(self):
        return self._format_object(self)

    def _format_object(self, obj, indent_level=0):
        spacing = "  " * indent_level
        inner_spacing = "  " * (indent_level + 1)
        
        if isinstance(obj, (SimpleNamespace, PluginConfig)):
            return self._format_namespace_object(obj, spacing, inner_spacing, indent_level)
        
        if isinstance(obj, Enum):
            return f'"{obj.name}"'
        
        if isinstance(obj, type):
            return f'"{obj.__name__}"'
        
        if isinstance(obj, str):
            return self._format_string_value(obj, inner_spacing)
        
        if isinstance(obj, Path):
            return f'"{str(obj)}"'
        
        if isinstance(obj, list):
            return self._format_list_value(obj, inner_spacing)
        
        return json.dumps(obj, ensure_ascii=False)

    def _format_namespace_object(self, obj, spacing, inner_spacing, indent_level):
        items = vars(obj).items()
        
        if not items:
            return f"{{}}"
        
        lines = ["{"]
        
        for k, v in items:
            formatted_v = self._format_object(v, indent_level + 1)
            lines.append(f'{inner_spacing}"{k}": {formatted_v},')
        
        lines[-1] = lines[-1].rstrip(',')
        lines.append(spacing + "}")
        return "\n".join(lines)

    def _format_string_value(self, obj, inner_spacing):
        if "\n" in obj:
            lines = obj.splitlines()
            indented_lines = []
            
            for line in lines:
                indented_lines.append(f"\n{inner_spacing}  " + line)
            
            content = "".join(indented_lines)
            return f'"""{content}\n{inner_spacing}"""'
        
        return f'"{obj}"'

    def _format_list_value(self, obj, inner_spacing):
        if not obj:
            return "[]"
        
        return json.dumps(obj, ensure_ascii=False)

    def to_dict(self):
        model_value = getattr(self, 'model', cfg.sys.config.MODEL_NAME_MAIN)
        use_json = getattr(self, 'use_json', False)
        format_value = "json" if use_json else ""
        options_value = vars(self.options) if hasattr(self, 'options') else {}
        prompt_value = getattr(self, 'prompt', "")
        
        messages_list = []
        messages_list.append({'role': 'system', 'content': prompt_value})
        
        return {
            "model": model_value,
            "format": format_value,
            "options": options_value,
            "messages": messages_list
        }

class AlisuConfig:
    """Alisu configuration manager class.
    
    Role: Manages plugin configurations, environment variables, and YAML.
    
    Methods:
        __init__(self) : Initialize the configuration object.
        _setup_system_info(self) : Setup system information including IP address.
        _generate_plugin_description_list(self) : Generate plugin description list.
        _sync_and_freeze_plugins(self) : Create folders and copy .env templates.
        _load_config_only(self) : Load environment variables into config objects.
        _load_agents(self) : Load all YAML configurations.
        _process_yaml_config(self, yaml_path, parent_obj) : Process a YAML configuration file.
        _apply_logic_to_agents(self, obj, replacements) : Apply replacement logic to agent prompts.
        _dict_to_namespace(self, data) : Recursively convert dict to SimpleNamespace.
        _parse_to_obj(self, path) : Parse .env file into the provided object.
    """
    def __init__(self):
        self.ROOT = Path(__file__).resolve().parent
        self.DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
        self.plugins_ROOT = self.DATA_DIR / "plugins"
        self.USERS_DIR = self.DATA_DIR / "Users"
        self.replacements = {}
        self.descriptions = []
        self.cfg = PluginConfig()
        self.cfg.DATA_DIR = self.DATA_DIR
        self.cfg.ROUTER = {}
        self.cfg.root = self.ROOT
        self.cfg.LOADED_PLUGINS = []
        self.cfg.RETURN_CODE = ReturnCode
        self._sync_and_freeze_plugins()
        self._migrate_all_user_schemas()
        self._load_config_only()
        self._load_users_config()
        self._generate_plugin_description_list()
        self._load_agents()
        self._setup_system_info()

    def _deep_update_missing(self, source, target):
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target.get(key), dict):
                self._deep_update_missing(value, target[key])
        return target

    def _migrate_all_user_schemas(self):
        root_dir = Path(__file__).resolve().parent
        data_users_dir = Path.home() / "Documents" / "ALISU_DATA" / "Users" #
        master_schema = {}
        
        root_cfg = root_dir / "user_config.yaml"
        if root_cfg.exists():
            with open(root_cfg, 'r', encoding='utf-8') as f:
                master_schema = self._deep_update_missing(yaml.safe_load(f) or {}, master_schema)

        plugins_path = root_dir / "plugins" #
        if plugins_path.exists():
            for plugin_dir in plugins_path.iterdir():
                if plugin_dir.is_dir():
                    p_user_cfg = plugin_dir / "user_config.yaml"
                    if p_user_cfg.exists():
                        with open(p_user_cfg, 'r', encoding='utf-8') as f:
                            plugin_data = yaml.safe_load(f) or {}
                            master_schema = self._deep_update_missing(plugin_data, master_schema)

        if not master_schema:
            return

        if not data_users_dir.exists():
            data_users_dir.mkdir(parents=True, exist_ok=True)
        
        system_user_file = data_users_dir / "system.yaml"
        
        if not system_user_file.exists():
            default_system_content = {"system": master_schema}
            with open(system_user_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_system_content, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"User config system created : {system_user_file.name}")


        for user_file in data_users_dir.glob("*.yaml"):
            with open(user_file, 'r', encoding='utf-8') as f:
                try:
                    user_content = yaml.safe_load(f) or {}
                except Exception as e:
                    continue

            modified = False
            for username in user_content:
                if isinstance(user_content[username], dict):
                    user_content[username] = self._deep_update_missing(master_schema, user_content[username])
                    modified = True

            if modified:
                with open(user_file, 'w', encoding='utf-8') as f:
                    yaml.dump(user_content, f, default_flow_style=False, allow_unicode=True)

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
        
        all_lines += "NONE: Nonsense, philosophy, or no clear action"
        self.replacements["REPLACE_PLUGINS"] = all_lines
        return

    def _dict_to_namespace(self, data):
        if isinstance(data, dict):
            result_dict = {}
            
            for k, v in data.items():
                result_dict[k] = self._dict_to_namespace(v)
            
            return PluginConfig(**result_dict)
        
        if isinstance(data, list):
            result_list = []
            
            for item in data:
                result_list.append(self._dict_to_namespace(item))
            
            return result_list
        
        return data

    def _parse_to_obj(self, path):
        if not path.exists():
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        for l0_key, l1_data in data.items():
            if not isinstance(l1_data, dict):
                setattr(self.cfg, l0_key, l1_data)
                continue
            
            self._process_config_section(l1_data, l0_key)
            
            new_data_ns = self._dict_to_namespace(l1_data)
            self._update_cfg_attribute(l0_key, new_data_ns)

    def _process_config_section(self, l1_data, l0_key):
        for l1_key, l2_data in l1_data.items():
            if l1_key.startswith("config"):
                if isinstance(l2_data, dict):
                    self._handle_config_keys(l2_data, l0_key)
                    self._handle_bypass_router(l2_data, l0_key)

    def _handle_config_keys(self, l2_data, l0_key):
        if "DESCRIPTION" in l2_data.keys():
            if l2_data['DESCRIPTION']:
                self.descriptions.append(f"{l0_key.upper()}: {l2_data['DESCRIPTION']}")
        
        for key, value in l2_data.items():
            if "REPLACE_" in key:
                self.replacements[key.upper()] = value

    def _handle_bypass_router(self, l2_data, l0_key):
        if "BYPASS_ROUTER" in l2_data.keys():
            content = l2_data["BYPASS_ROUTER"]
            final_list = []
            
            if isinstance(content, list):
                final_list = content
            elif isinstance(content, dict):
                for sub_list in content.values():
                    if isinstance(sub_list, list):
                        final_list.extend(sub_list)
            
            if final_list:
                self.cfg.ROUTER[l0_key.upper()] = final_list

    def _update_cfg_attribute(self, l0_key, new_data_ns):
        if hasattr(self.cfg, l0_key):
            existing_obj = getattr(self.cfg, l0_key)
            
            if isinstance(existing_obj, (SimpleNamespace, PluginConfig)) and isinstance(new_data_ns, (SimpleNamespace, PluginConfig)):
                for k, v in vars(new_data_ns).items():
                    setattr(existing_obj, k, v)
            else:
                setattr(self.cfg, l0_key, new_data_ns)
        else:
            setattr(self.cfg, l0_key, new_data_ns)

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

    def _load_config_only(self):
        global_config = self.DATA_DIR / "config.yaml"
        
        if not global_config.exists():
            shutil.copy("config_example.yaml", global_config)
        
        self._parse_to_obj(global_config)
        
        for name in self.cfg.LOADED_PLUGINS:
            config_path = self.plugins_ROOT / name / "config.yaml"
            
            if config_path.exists():
                self._parse_to_obj(config_path)
            else:
                logger.info(f'SYSTEM : Please copy update configfile in {config_path}')

    def _load_users_config(self):
        if not self.USERS_DIR.exists():
            self.USERS_DIR.mkdir(parents=True, exist_ok=True)
            return

        user_files = self.USERS_DIR.glob("*.yaml")
        for user_file in user_files:
            with open(user_file, 'r', encoding='utf-8') as f:
                try:
                    data = yaml.safe_load(f) or {}
                    for username, user_data in data.items():
                        ns_user_data = self._dict_to_namespace(user_data)
                        setattr(self.cfg, username, ns_user_data)
                except Exception as e:
                    logger.error(f"Failed to load user profile {user_file.name}: {e}")

    def _load_agents(self):
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
                    val_str = self._format_replacement_value(r_val)
                    obj.prompt = obj.prompt.replace(r_key, val_str)
            return

        if isinstance(obj, (SimpleNamespace, PluginConfig)):
            for k in vars(obj):
                self._apply_logic_to_agents(getattr(obj, k))
        elif isinstance(obj, list):
            for item in obj:
                self._apply_logic_to_agents(item)

    def _format_replacement_value(self, r_val):
        if isinstance(r_val, list):
            val_str = ", ".join(map(str, r_val))
        else:
            val_str = str(r_val)
        return val_str


def print_config_paths(obj, current_path="cfg"):
    if isinstance(obj, (SimpleNamespace, PluginConfig)):
        for key, value in vars(obj).items():
            print_config_paths(value, f"{current_path}.{key}")
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            print_config_paths(item, f"{current_path}[{i}]")
    
    else:
        logger.info(f"{current_path}")

import sys
cfg = AlisuConfig().cfg

cfg.debug = 1 if "-d" in sys.argv or "--debug" in sys.argv else 0
cfg.verbose = 1 if "-v" in sys.argv or "--verbose" in sys.argv else 0
cfg.report = 1 if "-r" in sys.argv or "--report" in sys.argv else 0
cfg.no_bypass = 0 if "--no-bypass" in sys.argv else 1

if not cfg.no_bypass:
    logger.info("--- BYPASS DISABLED ---")
if cfg.debug:
    logger.info("--- DEBUG MODE ENABLED ---")
if cfg.verbose:
    logger.info("--- VERBOSE MODE ENABLED ---")
