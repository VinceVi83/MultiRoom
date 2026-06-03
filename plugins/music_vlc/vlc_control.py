import os
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
    Also controls system volume via PulseAudio/PipeWire with automatic sink detection.
    
    Methods:
        __init__(self, cfg, index, playlist="") : Initialize VLC control instance with config.
        _vlc_request(self, endpoint, params=None) : Make HTTP request to VLC control port.
        handle_simple_command(self, action) : Handle simple VLC commands via command mapping.
        _detect_audio_sink(self) : Automatically detect the best audio sink to use.
        _control_system_volume(self, action) : Control system volume using PulseAudio/PipeWire.
        empty_current_playlist(self) : Empty the current playlist.
        change_playlist(self, target) : Change the current playlist to target path.
        start_vlc(self, path="default") : Start VLC with given playlist path and set system volume to 100%.
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
        self.audio_sink = None

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
        if action in ["VOL_DOWN", "VOL_UP"]:
            return self._control_system_volume(action)
        
        cmd = self.vlc_commands.get(action)
        if cmd:
            return self._vlc_request("status.xml", f"command={cmd}")
        return None

    def _run_pactl_command(self, args, check=True):
        env = os.environ.copy()
        env['XDG_RUNTIME_DIR'] = '/run/user/1000'
        env['PULSE_SERVER'] = 'unix:/run/user/1000/pulse/native'
        
        try:
            result = subprocess.run(
                ["pactl"] + args,
                capture_output=True,
                text=True,
                check=check,
                env=env
            )
            return result
        except subprocess.CalledProcessError as e:
            if check:
                raise
            return e

    def _detect_audio_sink(self):
        try:
            try:
                self._run_pactl_command(["get-sink-volume", "@DEFAULT_SINK@"])
                return "@DEFAULT_SINK@"
            except subprocess.CalledProcessError:
                pass

            result = self._run_pactl_command(["list", "short", "sinks"])
            
            lines = result.stdout.strip().split('\n')
            if lines:
                first_sink_index = lines[0].split('\t')[0]
                logger.info(f"Using first available audio sink: {first_sink_index}")
                return first_sink_index
            
            logger.error("No audio sinks found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to detect audio sink: {e}")
            return None

    def _control_system_volume(self, action):
        try:
            if self.audio_sink is None:
                self.audio_sink = self._detect_audio_sink()
                if self.audio_sink is None:
                    return None
            
            result = self._run_pactl_command(["get-sink-volume", self.audio_sink])

            import re
            match = re.search(r'/\s*(\d+)%', result.stdout)
            if not match:
                match = re.search(r'(\d+)%', result.stdout)
            
            if not match:
                logger.error(f"Could not parse current volume. Output: {result.stdout}")
                return None
            
            current_volume = int(match.group(1))
            
            step = 10
            if action == "VOL_DOWN":
                new_volume = max(0, current_volume - step)
            else:
                new_volume = min(100, current_volume + step)

            self._run_pactl_command(["set-sink-volume", self.audio_sink, f"{new_volume}%"])
            
            logger.info(f"System volume changed from {current_volume}% to {new_volume}% (sink: {self.audio_sink})")
            return f"Volume system modified: {current_volume}% -> {new_volume}%"
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to control system volume: {e}. stderr: {e.stderr}")
            return None
        except FileNotFoundError:
            logger.error("pactl not found. Is PulseAudio/PipeWire installed?")
            return None
        except Exception as e:
            logger.error(f"Error controlling volume: {e}")
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

        custom_env = os.environ.copy()
        custom_env["XDG_RUNTIME_DIR"] = "/run/user/1000"
        sout_param = f"#duplicate{{dst=display,dst=std{{access=http,mux=ogg,dst=0.0.0.0:{self.port_stream}}}}}"
        
        args = [
            "vlc",
            "--playlist-enqueue", path,
            "--no-video",
            "--aout", "pulse",
            f"--http-port={self.port_ctrl}",
            "--sout", sout_param,
            "-I", "dummy",
            "--extraintf", "http",
            "--http-password", self.password
        ]

        try:
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=custom_env
            )
            self.is_initialized = True
            self.is_playing = True
            time.sleep(5)

            try:
                self.audio_sink = self._detect_audio_sink()
                if self.audio_sink is None:
                    raise Exception("No audio sink detected")
                
                self._run_pactl_command(["set-sink-volume", self.audio_sink, "100%"])
                logger.info(f"System volume set to 100% after VLC startup (sink: {self.audio_sink})")
            except Exception as e:
                logger.error(f"Failed to set volume to 100%: {e}")
            
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
            time_val = root.findtext('time', '0')
            length_val = root.findtext('length', '0')
            state_val = root.findtext('state', 'unknown')
            
            return {
                "time": int(time_val),
                "length": int(length_val),
                "state": state_val.lower()
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

    def get_current_state(self):
        xml_data = self._vlc_request("status.xml")
        parsed_data = self._parse_status_xml(xml_data)
        
        if parsed_data is None:
            return "unknown"
        
        return parsed_data["state"]

    def __del__(self):
        self.kill_vlc()
