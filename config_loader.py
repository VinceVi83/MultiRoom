import os, yaml, socket, getpass, psutil
from pathlib import Path
from types import SimpleNamespace
from enum import Enum
from dotenv import load_dotenv, dotenv_values

class ReturnCode(Enum):
    SUCCESS = 1
    ERR = 2
    ERR_NOT_CONNECTED = 3
    ERR_NOT_IMPLEMENTED = 4
    ERR_ALREADY_DONE = 5
    ERR_UNKNOWN_DEVICE = 6
    ERR_INVALID_ARGUMENT = 7
    ERR_NOT_CONFIGURED = 8
    NULL = 9

class AlisuConfig:
    def __init__(self):
        self.ROOT = Path(__file__).resolve().parent
        self.DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
        self.ENV_PATH = self.DATA_DIR / ".env"
        self.YAML_PATH = self.ROOT / 'agents_config.yaml'
        
        self.cfg = SimpleNamespace()
        
        self._load_environment()
        self._load_agents_yaml()
        self._setup_system_info()
        self._map_playlists()
        self._finalize_prompts()

    def _load_environment(self):
        load_dotenv(self.ENV_PATH)
        env_vars = dotenv_values(self.ENV_PATH)
        
        for k, v in env_vars.items():
            if v is None: continue
            key, val = k.upper(), v.strip()
            
            if ',' in val:
                if ':' in val:
                    parsed = {i.split(':')[0].strip(): i.split(':')[1].strip() for i in val.split(',') if ':' in i}
                else:
                    parsed = [i.strip() for i in val.split(',') if i.strip()]
            else:
                parsed = val
            
            setattr(self.cfg, key, parsed)

    def _dict_to_ns(self, d):
        if not isinstance(d, dict): return d
        defaults = {"model": os.getenv("MODEL_NAME_MAIN"), "use_json": True}
        merged = {**defaults, **d}
        return SimpleNamespace(**{k: (self._dict_to_ns(v) if k != "options" else v) for k, v in merged.items()})

    def _load_agents_yaml(self):
        if not self.YAML_PATH.exists():
            raise FileNotFoundError(f"CRITICAL: YAML config missing at {self.YAML_PATH}")

        with open(self.YAML_PATH, 'r', encoding='utf-8') as f:
            try:
                data = yaml.safe_load(f) or {}
            except yaml.YAMLError as exc:
                print(f"\n[!!!] YAML SYNTAX ERROR in {self.YAML_PATH}")
                raise exc 
            
            if not data:
                raise ValueError(f"CRITICAL: {self.YAML_PATH} is empty!")

            for k, v in data.items():
                setattr(self.cfg, k, self._dict_to_ns(v))

    def _setup_system_info(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            self.cfg.INTERFACE_IP = s.getsockname()[0]
        except:
            self.cfg.INTERFACE_IP = "127.0.0.1"
        finally:
            s.close()
        self.cfg.RETURN_CODE = ReturnCode
        
    def _map_playlists(self):
        p_dir = Path(getattr(self.cfg, 'DIR_DOCS', self.DATA_DIR)) / "Playlists"
        self.cfg.PLAYLIST_DIR = p_dir
        self.cfg.PLAYLIST_LIST = {i.name: i for i in p_dir.iterdir()} if p_dir.exists() else {}

    def _finalize_prompts(self):
        playlists_str = "\n".join([f"- {name}" for name in self.cfg.PLAYLIST_LIST])
        self.cfg.RouterLLM_SUB.PLAYLIST_AGENT.prompt = \
            self.cfg.RouterLLM_SUB.PLAYLIST_AGENT.prompt.replace("REPLACE", playlists_str)

        loc_val = self.cfg.REPLACE_LOCATION
        
        if isinstance(loc_val, list):
            loc_val = ", ".join(loc_val)
            
        self.cfg.GlobalLLM.location_agent.prompt = \
            self.cfg.GlobalLLM.location_agent.prompt.replace("REPLACE_LOCATIONS", loc_val)

        self.cfg.routing_table = {
            "DOMOTIC_AGENT": {
                "agent": self.cfg.RouterLLM_SUB.DOMOTIC_AGENT,
                "mapping": getattr(self.cfg, 'DICO_SUB_DOMOTIC', {}),
                "labels": list(getattr(self.cfg, 'DICO_SUB_DOMOTIC', {}).values())
            },
            "INFO_AGENT": {
                "agent": self.cfg.RouterLLM_SUB.INFO_AGENT,
                "mapping": getattr(self.cfg, 'DICO_SUB_INFO', {}),
                "labels": list(getattr(self.cfg, 'DICO_SUB_INFO', {}).values())
            },
            "CALENDAR_AGENT": {
                "agent": self.cfg.RouterLLM_SUB.CALENDAR_AGENT,
                "mapping": getattr(self.cfg, 'DICO_SUB_CALENDAR', {}),
                "labels": list(getattr(self.cfg, 'DICO_SUB_CALENDAR', {}).values())
            },
            "DAILY_AGENT": {
                "agent": self.cfg.RouterLLM_SUB.DAILY_AGENT,
                "mapping": getattr(self.cfg, 'DICO_SUB_DAILY', {}),
                "labels": list(getattr(self.cfg, 'DICO_SUB_DAILY', {}).values())
            },
            "MUSIC_AGENT": {
                "agent": self.cfg.RouterLLM_SUB.MUSIC_AGENT,
                "mapping": getattr(self.cfg, 'DICO_SUB_MUSIC', {}),
                "labels": list(getattr(self.cfg, 'DICO_SUB_MUSIC', {}).values())
            },
            "VLC_AGENT": {
                "agent": self.cfg.RouterLLM_SUB.VLC_AGENT,
                "mapping": getattr(self.cfg, 'DICO_SUB_VLC', {}),
                "labels": list(getattr(self.cfg, 'DICO_SUB_VLC', {}).values())
            }
        }
        self.cfg.SUB_MAPPINGS = {k: v["mapping"] for k, v in self.cfg.routing_table.items()}

alisu_loader = AlisuConfig()
cfg = alisu_loader.cfg