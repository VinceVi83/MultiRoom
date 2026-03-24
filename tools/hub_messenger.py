import socket
import ssl
import uuid
import hashlib
import platform
import subprocess
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, HTTPServer

class HubMessenger:
    """Hub Messenger Service
    
    Role: Manages secure communication with the hub server including authentication, text-to-speech (STT) and push-to-talk (PTT) file transfers via SSL/TLS.
    
    Methods:
        __init__(self, host, port, cert_path, user='test', password='test') : Initialize the messenger with connection settings.
        _get_hw_sign(self) : Generate hardware signature for authentication.
        _get_secure_context(self) : Create SSL context for secure connections.
        _authenticate(self, ssock) : Authenticate with the hub server.
        _send_raw(self, tag, content, wait_response=False) : Send raw packets to the hub.
        send_stt(self, text, wait_response=False) : Send text-to-speech request.
        send_ptt(self, file_path) : Send push-to-talk file via HTTP server.
    """
    
    def __init__(self, host="172.21.8.200", port=28888, cert_path=None, user="test", password="test"):
        self.host = host
        self.port = port
        self.http_port = 8090
        self.user = user
        self.password = password
        self.hw_signature = self._get_hw_sign()
        print(f"Add this {self.hw_signature} in LIST_ALLOWED_SIGS in your .env")
        
        self.cert_file = self._resolve_cert_path(cert_path)
        self.key_file = self.cert_file.replace("cert.pem", "key.pem") if self.cert_file else None
        
        self.ssl_context = self._get_secure_context()
        self._ssock = None

    def _resolve_cert_path(self, cert_path):
        if cert_path and os.path.exists(cert_path):
            return cert_path
        
        try:
            from config_loader import cfg
            path_from_cfg = os.path.join(cfg.DATA_DIR, "Certification", "cert.pem")
            if os.path.exists(path_from_cfg):
                return path_from_cfg
        except ImportError:
            print("[HubMessenger] Cannot import config_loader.")
        except Exception as e:
            print(f"[HubMessenger] Config error: {e}")

        local_fallback = os.path.join("Certification", "cert.pem")
        if os.path.exists(local_fallback):
            return local_fallback
            
        return ""

    def is_wsl():
        wsl_files = glob.glob("/proc/sys/fs/binfmt_misc/WSL*")
        if len(wsl_files) > 0:
            return True
        if "microsoft" in platform.release().lower():
            return True    
        return False

    def _get_hw_sign(self):
        try:
            system = platform.system().lower()
            node_name = platform.node()
            is_wsl = "microsoft" in platform.release().lower() or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")

            if is_wsl:
                cmd = "powershell.exe -Command \"(Get-CimInstance Win32_ComputerSystemProduct).UUID\""
                seed = subprocess.check_output(cmd, shell=True).decode().strip()
                if not seed: seed = node_name
                print(f"[*] Signature: WSL Mode")

            elif "android" in sys.platform.lower() or os.path.exists("/system/build.prop"):
                try:
                    seed = subprocess.check_output("getprop ro.serialno", shell=True).decode().strip()
                except:
                    seed = subprocess.check_output("getprop ro.build.id", shell=True).decode().strip()
                print(f"[*] Signature: Android Mode")

            elif system == "linux":
                if os.path.exists("/etc/machine-id"):
                    with open("/etc/machine-id", "r") as f:
                        seed = f.read().strip()
                else:
                    seed = node_name
                print(f"[*] Signature: Linux Mode")

            else:
                os_id = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].strip()
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> e) & 0xff) for e in range(0, 48, 8)][::-1])
                seed = f"{os_id}-{mac}"
                print(f"[*] Signature: Windows Mode")
            
            sign = hashlib.sha256(seed.encode()).hexdigest()
            return sign

        except Exception:
            return hashlib.sha256(platform.node().encode()).hexdigest()

    def _get_secure_context(self):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        
        if self.cert_file and os.path.exists(self.cert_file):
            try:
                ctx.load_verify_locations(cafile=self.cert_file)
                ctx.verify_mode = ssl.CERT_REQUIRED
            except Exception as e:
                print(f"Certificate load error: {e}")
                ctx.verify_mode = ssl.CERT_NONE
        else:
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _get_connection(self):
        if self._ssock:
            return self._ssock

        try:
            sock = socket.create_connection((self.host, self.port), timeout=10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            ssock = self.ssl_context.wrap_socket(sock, server_hostname=self.host)
            
            if self._authenticate(ssock):
                self._ssock = ssock
                return self._ssock
            else:
                ssock.close()
                return None
        except Exception as e:
            print(f"[!] Connection error: {e}")
            return None

    def _authenticate(self, ssock):
        auth_packet = f"{self.hw_signature}:Auth:{self.user}:{self.password}\n"
        ssock.sendall(auth_packet.encode('utf-8'))
        
        raw_response = ssock.recv(4096).decode('utf-8').strip()
        
        valid_responses = ["AUTH_OK", "ALREADY_AUTH", "AUTH_SUCCESS"]
        if any(word in raw_response for word in valid_responses):
            return True
        return False

    def _send_raw(self, tag, content, wait_response=False):
        packet = f"{self.hw_signature}:{tag}:{content}\n"
        
        ssock = self._get_connection()
        if not ssock:
            return None

        try:
            ssock.sendall(packet.encode('utf-8'))
            
            if wait_response:
                ssock.settimeout(30)
                response = ssock.recv(4096).decode('utf-8').strip()
                return response
            return True

        except (socket.error, ssl.SSLError) as e:
            print(f"[!] Disconnection detected ({e}). Attempting reconnection...")
            self._ssock = None
            return self._send_raw(tag, content, wait_response)


    def send_stt(self, text, wait_response=False):
        return self._send_raw("test", text, wait_response)

    def send_ptt(self, file_path):
        if not os.path.exists(file_path): return False

        filename = os.path.basename(file_path)
        directory = os.path.dirname(os.path.abspath(file_path))
        
        os.chdir(directory)
        httpd = HTTPServer(('0.0.0.0', self.http_port), SimpleHTTPRequestHandler)
        
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        if os.path.exists(self.cert_file) and os.path.exists(self.key_file):
            context.load_cert_chain(self.cert_file, self.key_file)
            httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

        ip = socket.gethostbyname(socket.gethostname())
        url = f"https://{ip}:{self.http_port}/{filename}"
        
        def serve():
            httpd.handle_request()
            httpd.server_close()

        server_thread = threading.Thread(target=serve, daemon=True)
        server_thread.start()

        self._send_raw("PTT", url)

        server_thread.join()
        return True
