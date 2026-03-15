"""
Constants and configuration management.
"""
import os
import re
from pathlib import Path
from types import SimpleNamespace
import netifaces as ni  # type: ignore
from dotenv import load_dotenv # type: ignore

# Chargement du fichier .env
ENV_PATH = Path(__file__).parent.parent / '.env'
load_dotenv()
def get_var_environment(var, default=""):
    """Fetch environment variable and strip whitespace."""
    return os.getenv(var, default).strip()
cfg = SimpleNamespace(**{k: get_var_environment(k) for k in ENV_KEYS})

USERS = {
    "test": "test"
}

# PEP 8: Les constantes globales sont en UPPER_CASE
RETURN_CODE = SimpleNamespace(
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





# Liste des clés à récupérer
ENV_KEYS = [
    "interface", "user_vlc", "pwd_vlc", "user_linux", "pwd_linux",
    "music_folder_1", "music_folder_2", "config_multiroom",
    "path_music", "path_trash_music", "path_music_filtred", "path_playlist"
]

# cfg (Configuration) regroupé dans un namespace


# Détermination de l'IP locale
try:
    local_ip = ni.ifaddresses(cfg.interface)[ni.AF_INET][0]['addr']
except (KeyError, ValueError, Exception):
    local_ip = "127.0.0.1"
    print(f"Warning: Interface {cfg.interface} not found, fallback to 127.0.0.1")

# Chemins dérivés
PATH_HOME = f"/home/{cfg.user_linux}/"
PATH_CRON = "/var/spool/cron/crontabs/"

vlc = {
    "1": "pl_pause",
    "2": "pl_previous",
    "3": "pl_next",
    "4": "volume&val=-30",
    "5": "volume&val=+30",
    "6": "pl_random",
    "7": "status.xml",
    "playlist": "",
    'dir': "in_play&input=",
    'pwd': cfg.pwd_vlc,
    'user': cfg.user_vlc
}

linux = {
    'pwd': cfg.pwd_linux,
    'user': cfg.user_linux,
    'home': PATH_HOME,
    'cron': PATH_CRON,
    'playlist': cfg.path_playlist
}

playlist = {
    "default": "/home/shireikan/ProjectLinux/MultiRoom_Test/Default",
    "touhou": "/home/shireikan/ProjectLinux/MultiRoom_Test/Touhou",
    "rock": "/home/shireikan/ProjectLinux/MultiRoom_Test/Rock"
}

mutagen_keys = {
    'TIT2': 'title',
    'TPE1': 'artist',
    'TALB': 'album',
    'TPE2': 'circle',
    'TCON': 'genre',
    'COMM': 'comment',
    'TLAN': 'language'
}

list_rpis = []


def escape_path(text):
    """Escapes special characters in a path string."""
    return re.escape(text)


CHARS_TO_ESCAPE = "+-][ )(^$*."
ESCAPE_CHAR_MAP = {c: f"\\{c}" for c in CHARS_TO_ESCAPE}