import subprocess
import xml.etree.ElementTree as ET
import urllib.parse
import requests
from requests.auth import HTTPBasicAuth
import time
import logging
logger = logging.getLogger(__name__)

class VLCControl:
    """VLC Media Player Control Service
    
    Role: Manages VLC media player instances via HTTP control interface for music playback.
    
    Methods:
        __init__(self, cfg, index, playlist="") : Initialize VLC control instance with config.
        _vlc_request(self, endpoint, params=None) : Make HTTP request to VLC control port.
        handle_simple_command(self, action) : Handle simple VLC commands via command mapping.
        change_playlist(self, target) : Change the current playlist to target path.
        start_vlc(self, path="default") : Start VLC with given playlist path.
        kill_vlc(self) : Stop and clean up VLC process.
        get_remaining_seconds(self) : Get remaining time for current track.
        get_total_remaining_seconds(self) : Get total remaining time including queue.
        get_current_state(self) : Get current playback state.
        _parse_status_xml(self, xml_data) : Parse status XML response.
        _parse_playlist_xml(self, xml_data) : Parse playlist XML response.
        set_vlc_loop(self, target_state: bool) : Set VLC loop state.
        __del__(self) : Cleanup on object deletion.
    """
    def __init__(self, cfg, index, playlist=""):
        self.index = index
        self.cfg = cfg
        self.process = None
        self.port_ctrl = str(int(self.cfg.config.VLC_PORT_START) + index)
        self.port_stream = str(int(self.cfg.config.VLC_PORT_START) + 1000 + index)
        self.password = getattr(self.cfg.security.VLC_USERS, "test", None)
        self.base_url = f"http://127.0.0.1:{self.port_ctrl}/requests"
        
        self.is_initialized = False
        self.is_playing = False
        self.current_path = playlist

        self.vlc_commands = {
            "TOGGLE": "pl_pause",
            "PREVIOUS": "pl_previous",
            "NEXT": "pl_next",
            "VOL_DOWN": "volume&val=-60",
            "VOL_UP": "volume&val=+60",
            "SHUFFLE": "pl_random",
            "INFO": "status.xml",
            "playlist": "",
            'dir': "in_play&input="
        }

        self.start_vlc(playlist)

    def _vlc_request(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        auth = HTTPBasicAuth('', self.password)
        
        try:
            response = requests.get(
                url, 
                params=params, 
                auth=auth, 
                timeout=5
            )
            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"VLC Error {response.status_code}: {response.reason}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Exception: {e}")
            return None

    def handle_simple_command(self, action):
        cmd = self.vlc_commands.get(action)
        if cmd:
            return self._vlc_request("status.xml", f"command={cmd}")
        return None

    def empty_current_playlist(self):
        self._vlc_request("status.xml", "command=pl_empty")

    def change_playlist(self, target):
        self.empty_current_playlist()
        self.current_path = target
        encoded_target = urllib.parse.quote(str(target))
        return self._vlc_request("status.xml", f"command=in_play&input={encoded_target}")

    def start_vlc(self, path="default"):
        self.current_path = path
        if self.process and self.process.poll() is None:
            return self.cfg.RETURN_CODE.SUCCESS

        sout_param = f"#duplicate{{dst=display,dst=std{{access=http,mux=ogg,dst=0.0.0.0:{self.port_stream}}}}}"
        
        args = [
            "vlc",
            "--playlist-enqueue", path,
            "--no-video",
            f"--http-port={self.port_ctrl}",
            "--sout", sout_param,
            "-I", "dummy",
            "--extraintf", "http",
            "--http-password", self.password
        ]

        try:
            self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.is_initialized = True
            self.is_playing = True
            time.sleep(5)
            return self.cfg.RETURN_CODE.SUCCESS
        except Exception:
            return self.cfg.RETURN_CODE.ERR

    def kill_vlc(self):
        if self.process:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                    self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
            finally:
                self.process = None

        self.is_initialized = False
        self.is_playing = False
        self.current_path = ""
        return self.cfg.RETURN_CODE.SUCCESS

    def _parse_status_xml(self, xml_data):
        if not xml_data:
            return None
        
        try:
            root = ET.fromstring(xml_data)
            return {
                "time": int(root.findtext('time', '0')),
                "length": int(root.findtext('length', '0')),
                "state": root.findtext('state', 'unknown').lower()
            }
        except Exception:
            return None

    def get_remaining_seconds(self):
        xml_data = self._vlc_request("status.xml")
        parsed_data = self._parse_status_xml(xml_data)
        
        if parsed_data is None:
            return -1
        
        curr_time = parsed_data["time"]
        total_length = parsed_data["length"]
        return max(0, total_length - curr_time)

    def get_total_remaining_seconds(self):
        current_remaining = self.get_remaining_seconds()
        xml_data = self._vlc_request("playlist.xml")
        
        if not xml_data:
            return current_remaining
        
        parsed_playlist = self._parse_playlist_xml(xml_data)
        total_after_current = parsed_playlist.get("total_after_current", 0) if parsed_playlist else 0
        
        return current_remaining + total_after_current

    def _parse_playlist_xml(self, xml_data):
        if not xml_data:
            return None
        
        try:
            root = ET.fromstring(xml_data)
            total_after_current = 0
            found_current = False
            
            for leaf in root.iter('leaf'):
                if leaf.get('current') == 'current':
                    found_current = True
                    continue
                
                if found_current:
                    duration_val = leaf.get('duration')
                    if duration_val:
                        total_after_current += int(duration_val)
                        
            return {"total_after_current": total_after_current}
        except Exception:
            return None

    def set_vlc_loop(self, target_state: bool):
        xml_data = self._vlc_request("status.xml")
        if not xml_data:
            return

        root = ET.fromstring(xml_data)
        loop_text = root.find('loop').text.lower()
        current_loop = (loop_text == 'true')

        if current_loop != target_state:
            self._vlc_request("status.xml?command=pl_loop")
        else:
            pass

    def get_current_state(self):
        xml_data = self._vlc_request("status.xml")
        parsed_data = self._parse_status_xml(xml_data)
        
        if parsed_data is None:
            return "unknown"
        
        return parsed_data["state"]

    def __del__(self):
        self.kill_vlc()
