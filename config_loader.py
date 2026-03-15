import os
import yaml
from pathlib import Path
from types import SimpleNamespace
from dotenv import load_dotenv, dotenv_values
import socket

ROOT = Path(__file__).resolve().parent
ENV_MAIN = ROOT / '.env'
YAML_CONFIG = ROOT / 'agents_config.yaml'
load_dotenv(ENV_MAIN)

def dict_to_ns(d):
    if isinstance(d, dict):
        defaults = {
            "model": os.getenv("MODEL_NAME_MAIN"),
            "use_json": False,
            "options": {},
            "prompt": ""
        }
        defaults.update(d)
        return SimpleNamespace(**{
            k: (dict_to_ns(v) if k != "options" else v)
            for k, v in defaults.items()
        })
    return d

env_vars = dotenv_values(ENV_MAIN)
base_dict = {}
for k, v in env_vars.items():
    if v is None: continue
    key = k.upper()
    val = v.strip()

    if key.startswith("DICO_"):
        try:
            dico_val = {}
            for item in val.split(','):
                if ':' in item:
                    sub_k, sub_v = item.split(':', 1)
                    dico_val[sub_k.strip()] = sub_v.strip()
            base_dict[key] = dico_val
        except Exception:
            base_dict[key] = val

    elif key.startswith("LIST_"):
        try:
            base_dict[key] = [item.strip() for item in val.split(',') if item.strip()]
        except Exception:
            base_dict[key] = val
    else:
        base_dict[key] = val

if YAML_CONFIG.exists():
    with open(YAML_CONFIG, 'r', encoding='utf-8') as f:
        yaml_data = yaml.safe_load(f) or {}
else:
    yaml_data = {}

cfg = SimpleNamespace(**base_dict)

import socket

def get_ip_python(interface=cfg.INTERFACE_NAME):
    try:
        import fcntl
        import struct
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
            s.fileno(),
            0x8915,
            struct.pack('256s', interface[:15].encode('utf-8'))
        )[20:24])
    except Exception:
        return None

cfg.INTERFACE_IP = get_ip_python()

for key, value in yaml_data.items():
    setattr(cfg, key, dict_to_ns(value))

def map_directory_contents(directory):
    path = Path(directory).expanduser().resolve()
    content_map = {}

    if not path.exists() or not path.is_dir():
        return content_map

    for item in path.iterdir():

        content_map[item.name] = item

    return content_map

cfg.PLAYLIST_DIR = Path(cfg.DIR_DOCS) / "Playlists"
cfg.PLAYLIST_LIST = map_directory_contents(cfg.PLAYLIST_DIR)
cfg.PLAYLIST_NAMES = list(cfg.PLAYLIST_LIST.keys())

cfg.RETURN_CODE = SimpleNamespace(
    SUCCESS=1,
    ERR=2,
    ERR_NOT_CONNECTED=3,
    ERR_NOT_IMPLEMENTED=4,
    ERR_DUPLICATE=5,
    ERR_ILLEGAL_IP=6,
    ERR_INVALID_ARGUMENT=7,
    ERR_NO_MUSIC_FILES=8,
    NULL=9
)

playlists_str = "\n".join([f"- {name}" for name in cfg.PLAYLIST_LIST])
current_prompt = cfg.RouterLLM_SUB.PLAYLIST_AGENT.prompt
cfg.RouterLLM_SUB.PLAYLIST_AGENT.prompt = current_prompt.replace("REPLACE", playlists_str)

current_prompt = cfg.GlobalLLM.location_agent.prompt
cfg.GlobalLLM.location_agent.prompt = current_prompt.replace("REPLACE_LOCATIONS", cfg.REPLACE_LOCATION)

# Construction de la table de routage fusionnée
cfg.routing_table = {
    "DOMOTIC_AGENT": {
        "agent": cfg.RouterLLM_SUB.DOMOTIC_AGENT,
        "mapping": cfg.DICO_SUB_DOMOTIC,
        "labels": list(cfg.DICO_SUB_DOMOTIC.values())
    },
    "INFO_AGENT": {
        "agent": cfg.RouterLLM_SUB.INFO_AGENT,
        "mapping": cfg.DICO_SUB_INFO,
        "labels": list(cfg.DICO_SUB_INFO.values())
    },
    "CALENDAR_AGENT": {
        "agent": cfg.RouterLLM_SUB.CALENDAR_AGENT,
        "mapping": cfg.DICO_SUB_CALENDAR,
        "labels": list(cfg.DICO_SUB_CALENDAR.values())
    },
    "DAILY_AGENT": {
        "agent": cfg.RouterLLM_SUB.DAILY_AGENT,
        "mapping": cfg.DICO_SUB_DAILY,
        "labels": list(cfg.DICO_SUB_DAILY.values())
    },
    "MUSIC_AGENT": {
        "agent": cfg.RouterLLM_SUB.MUSIC_AGENT,
        "mapping": cfg.DICO_SUB_MUSIC,
        "labels": list(cfg.DICO_SUB_MUSIC.values())
    },
    "VLC_AGENT": {
        "agent": cfg.RouterLLM_SUB.VLC_AGENT,
        "mapping": cfg.DICO_SUB_VLC,
        "labels": list(cfg.DICO_SUB_VLC.values())
    }
}

cfg.SUB_MAPPINGS = {k: v["mapping"] for k, v in cfg.routing_table.items()}
