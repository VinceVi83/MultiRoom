import os, sys, time, socket, queue, ssl, hashlib, uuid, platform, subprocess, argparse
import threading
import numpy as np
import wave
from http.server import SimpleHTTPRequestHandler, HTTPServer
from collections import deque
import pyaudio

from pathlib import Path

HUB_IP = "172.21.8.200"
HUB_PORT = 28888
HTTP_PORT = 8090
MICRO_GAIN = 3.0
is_windows = platform.system() == "Windows"

if is_windows:
    user_name = os.getlogin().lower()
    BASE_PATH = f"\\\\wsl$\\Ubuntu\\home\\{user_name}\\Documents\\ALISU_DATA"
    CERT_FILE = BASE_PATH + "\\Certification\\cert.pem"
    KEY_FILE = BASE_PATH + "\\Certification\\key.pem"
    WAV_PATH = BASE_PATH + "\\temp_voice.wav"
else:
    from config_loader import cfg
    CERT_FILE = str(cfg.DATA_DIR / "Certification" / "cert.pem")
    KEY_FILE = str(cfg.DATA_DIR / "Certification" / "key.pem")
    WAV_PATH = str(cfg.DATA_DIR / "temp_voice.wav")

class UnifiedSpeechSystem:
    """Unified Speech System
    
    Role: Manages voice capture, speech-to-text transcription, and push-to-talk recording operations.
    
    Methods:
        __init__(self, mode, is_linux=False) : Initialize the system with STT or PTT mode.
        run_unified_capture(self) : Run unified audio capture with VAD detection.
        _get_hw_sign(self) : Get hardware signature for authentication.
        _init_stt_assets(self) : Initialize speech-to-text assets (Whisper model).
        _init_ptt_assets(self) : Initialize push-to-talk assets (PyAudio).
        _get_ssl_context(self) : Get SSL context for client connections.
        _get_https_server_context(self) : Get SSL context for HTTPS server.
        _ensure_stt_connection(self) : Ensure STT connection to hub is active.
        send_packet(self, tag, content) : Send packet to hub with signature.
        start(self) : Start the main audio capture loop.
        _handle_stt_action(self, frames) : Handle speech-to-text transcription action.
        _handle_ptt_action(self, frames) : Handle push-to-talk recording and upload action.
    """
    def __init__(self, mode, is_linux=False):
        self.mode = mode
        self.is_linux = is_linux or (platform.system() == "Linux")
        self.hw_signature = self._get_hw_sign()
        self.running = True
        self.ssock = None
        self.temp_wav = WAV_PATH
        self.pre_roll = deque(maxlen=43)
        
        if self.mode == "stt":
            self._init_stt_assets()
        else:
            self._init_ptt_assets()

    def _get_hw_sign(self):
        try:
            if self.is_linux:
                with open("/etc/machine-id", "r") as f: os_id = f.read().strip()
            else:
                os_id = str(subprocess.check_output('wmic csproduct get uuid'), 'utf-8').split('\n')[1].strip()
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> e) & 0xff) for e in range(0, 48, 8)][::-1])
            return hashlib.sha256(f"{platform.node()}-{os_id}-{mac}".encode()).hexdigest()
        except:
            return hashlib.sha256(platform.node().encode()).hexdigest()

    def run_unified_capture(self):
        stream = self.pa.open(format=2, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        
        while self.running:
            frames, recording, silent_chunks = [], False, 0
            
            while self.running:
                data = stream.read(1024, exception_on_overflow=False)
                rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float64)**2))
                
                if rms > 500:
                    if not recording:
                        recording = True
                        frames.extend(list(self.pre_roll)) 
                        print("\n[VAD] Detection started (1s buffer included)")
                    
                    frames.append(data)
                    silent_chunks = 0
                elif recording:
                    frames.append(data)
                    silent_chunks += 1
                    if silent_chunks > 50: 
                        break
                else:
                    self.pre_roll.append(data)
            
            if frames and self.running:
                if self.mode == "ptt":
                    self._process_ptt_send(frames)
                else:
                    self._process_stt_transcribe(frames)
                
                frames = []
                recording = False
                self.pre_roll.clear()

    def _init_stt_assets(self):
        import sounddevice as sd
        from faster_whisper import WhisperModel
        self.sd = sd
        
        if not self.is_linux:
            possible_paths = [
                os.path.join(os.environ.get('APPDATA', ''), '..', 'Roaming', 'Python', 'Python312', 'site-packages', 'nvidia'),
                os.path.join(sys.prefix, 'Lib', 'site-packages', 'nvidia'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Python', 'Python312', 'Lib', 'site-packages', 'nvidia')
            ]
            
            for base in possible_paths:
                if os.path.exists(base):
                    for lib in ['cublas/bin', 'cudnn/bin', 'cuda_runtime/bin', 'cublas_cu12/bin']:
                        p = os.path.normpath(os.path.join(base, lib))
                        if os.path.exists(p):
                            os.add_dll_directory(p)
                            os.environ['PATH'] = p + os.pathsep + os.environ['PATH']
        
        has_gpu = subprocess.run(['nvidia-smi'], capture_output=True).returncode == 0
        dev = "cuda" if has_gpu else "cpu"
        comp = "float16" if dev == "cuda" else "int8"
        
        print(f"[*] Loading Whisper (Device: {dev})")
        try:
            self.model = WhisperModel("medium", device=dev, compute_type=comp)
        except Exception as e:
            print(f"[!] GPU Failed, falling back to CPU: {e}")
            self.model = WhisperModel("medium", device="cpu", compute_type="int8")
            
        self.audio_q = queue.Queue()

    def _init_ptt_assets(self):
        import pyaudio
        self.pa = pyaudio.PyAudio()

    def _get_ssl_context(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
            ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _get_https_server_context(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
            ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
        
        ctx.options |= ssl.OP_NO_SSLv2
        ctx.options |= ssl.OP_NO_SSLv3
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE 
        return ctx

    def _ensure_stt_connection(self):
        if self.ssock:
            try:
                self.ssock.send(b"") 
                return True
            except:
                self.ssock = None

        while self.running and not self.ssock:
            try:
                sock = socket.create_connection((HUB_IP, HUB_PORT), timeout=30)
                self.ssock = self._get_ssl_context().wrap_socket(sock, server_hostname=HUB_IP)
                auth = f"{self.hw_signature}:Auth:test:test"
                self.ssock.sendall(auth.encode('utf-8'))
                _ = self.ssock.recv(1024)
                return True
            except:
                time.sleep(5)
        return False

    def send_packet(self, tag, content):
        packet = f"{self.hw_signature}:{tag}:{content}\n"
        try:
            if self.mode == "stt":
                if self._ensure_stt_connection():
                    self.ssock.sendall(packet.encode('utf-8'))
                    response = self.ssock.recv(4096).decode('utf-8').strip()
                    return response
            else:
                with socket.create_connection((HUB_IP, HUB_PORT), timeout=10) as s:
                    with self._get_ssl_context().wrap_socket(s, server_hostname=HUB_IP) as ss:
                        ss.sendall(packet.encode('utf-8'))
        except Exception as e:
            print(f"[!] Send error: {e}")
        return None

    def start(self):
        self.pa = pyaudio.PyAudio()
        stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                             input=True, frames_per_buffer=1024)
        try:
            while self.running:
                frames, recording, silent_chunks = [], False, 0
                
                while self.running:
                    data = stream.read(1024, exception_on_overflow=False)
                    rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16).astype(np.float64)**2))
                    
                    if rms > 500 and not recording:
                        recording = True
                        frames.extend(list(self.pre_roll)) 
                        frames.append(data)
                        silent_chunks = 0
                    elif recording:
                        frames.append(data)
                        if rms < 350:
                            silent_chunks += 1
                        else:
                            silent_chunks = 0
                        if silent_chunks > 25 or len(frames) > 215:
                            break
                    else:
                        self.pre_roll.append(data)
                    
                    print(f" {'[REC]' if recording else '[IDLE]'} | RMS: {int(rms)} | Len: {len(frames)}", end="\r")

                if frames and self.running:
                    print(f"\n[INFO] Send complete ({len(frames)} chunks)")
                    if self.mode == "ptt":
                        self._handle_ptt_action(frames)
                    else:
                        self._handle_stt_action(frames)
                    
                    frames, recording = [], False
                    self.pre_roll.clear()

        finally:
            stream.stop_stream()
            stream.close()
            self.pa.terminate()

    def _handle_stt_action(self, frames):
        audio_np = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.model.transcribe(audio_np, language="en")
        text = " ".join([s.text for s in segments]).strip()
        
        if text:
            print(f"\n[STT] Received: {text}")
            self.send_packet("test", text)
        else:
            print("\n[STT] ??? (Noise detected but no text)")

    def _handle_ptt_action(self, frames):
        with wave.open(self.temp_wav, 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
        
        filename = os.path.basename(self.temp_wav)
        directory = os.path.dirname(os.path.abspath(self.temp_wav))

        def run_server():
            os.chdir(directory)
            server_address = ('0.0.0.0', HTTP_PORT)
            httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)
            httpd.socket = self._get_https_server_context().wrap_socket(httpd.socket, server_side=True)
            httpd.handle_request()
            httpd.server_close()

        threading.Thread(target=run_server, daemon=True).start()
        ip = socket.gethostbyname(socket.gethostname())
        url = f"https://{ip}:{HTTP_PORT}/{filename}"
        time.sleep(0.5)
        self.send_packet("PTT", url)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("-m", "--mode", choices=['stt', 'ptt'], required=True, help="Mode: stt (Whisper) or ptt (WAV)")
    parser.add_argument("-L", "--linux", action="store_true", help="Force Linux mode")
    
    try:
        args = parser.parse_args()
    except SystemExit:
        print("\n[!] Error: You must provide a mode.")
        parser.print_help()
        sys.exit(0)

    UnifiedSpeechSystem(mode=args.mode, is_linux=args.linux).start()
