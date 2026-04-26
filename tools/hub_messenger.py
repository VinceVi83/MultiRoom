import socket
import ssl
import uuid
import hashlib
import platform
import subprocess
import os
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import glob
import sys
from pathlib import Path
import argparse
import logging
logger = logging.getLogger(__name__)

class HubMessenger:
    """Hub Messenger Service Plugin
    
    Role: Manages secure socket connections and message transmission to hub.
    
    Methods:
        __init__(self, host, port, cert_path, user, password) : Initialize messenger with connection settings.
        _resolve_cert_path(self, cert_path) : Resolve certificate file path.
        is_wsl(self) : Check if running in WSL environment.
        _get_hw_sign(self) : Get hardware signature for authentication.
        _get_secure_context(self) : Create SSL context for secure connections.
        _get_connection(self) : Establish secure socket connection.
        _authenticate(self, ssock) : Authenticate with remote server.
        _send_raw(self, tag, content, wait_response) : Send raw message packet.
        send_stt(self, text, wait_response) : Send single text to speech message.
        send_multiple_stt(self, text, wait_response) : Send multiple text to speech messages.
        send_ptt(self, file_path) : Send push-to-talk file via HTTP server.
    """
    def __init__(self, host="127.0.0.1", port="28888", cert_path=None, user="test", password="test"):
        self.host = host
        self.port = int(port)
        self.http_port = 8100
        self.user = user
        self.password = password
        self.hw_signature = self._get_hw_sign()
        resolved = self._resolve_cert_path(cert_path)

        if resolved:
            self.cert_file = Path(resolved)
            if isinstance(self.cert_file, Path):
                self.key_file = self.cert_file.with_name("key.pem")
            else:
                self.key_file = Path(str(self.cert_file)).with_name("key.pem")
            
        self.ssl_context = self._get_secure_context()
        self._ssock = None
        self._server_thread = None

    def _resolve_cert_path(self, cert_path):
        if cert_path and os.path.exists(cert_path):
            return cert_path
        else:
            try:
                from config_loader import cfg
                cert_path = Path(cfg.DATA_DIR) / "Certification" / "cert.pem"
                path_from_cfg = os.path.join(cfg.DATA_DIR, "Certification", "cert.pem")
                if os.path.exists(path_from_cfg):
                    return path_from_cfg
            except:
                pass
        local_fallback = os.path.join("Certification", "cert.pem")
        if os.path.exists(local_fallback):
            return local_fallback
            
        return ""

    def is_wsl(self):
        return "microsoft" in platform.release().lower() or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")

    def _get_hw_sign(self):
        try:
            system = platform.system().lower()
            node_name = platform.node()
            if self.is_wsl():
                cmd = "powershell.exe -Command \"(Get-CimInstance Win32_ComputerSystemProduct).UUID\""
                seed = subprocess.check_output(cmd, shell=True).decode().strip()
                if not seed: seed = node_name
            
            elif "android" in sys.platform.lower() or os.path.exists("/system/build.prop"):
                try:
                    seed = subprocess.check_output("getprop ro.serialno", shell=True).decode().strip()
                except:
                    seed = subprocess.check_output("getprop ro.build.id", shell=True).decode().strip()

            elif system == "linux":
                if os.path.exists("/etc/machine-id"):
                    with open("/etc/machine-id", "r") as f:
                        seed = f.read().strip()
                else:
                    seed = node_name
            
            else:
                os_id = subprocess.check_output('wmic csproduct get uuid').decode().split('\n')[1].strip()
                mac = ':'.join(['{:02x}'.format((uuid.getnode() >> e) & 0xff) for e in range(0, 48, 8)][::-1])
                seed = f"{os_id}-{mac}"
            
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
                logger.error(f"Certificate load error: {e}")
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
            logger.error(f"[!] Connection error: {e}")
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
            logger.error(f"[!] Disconnection detected ({e}). Attempting reconnection...")
            self._ssock = None
            return self._send_raw(tag, content, wait_response)


    def send_stt(self, text, wait_response=False):
        if "\n" in text:
            return self.send_multiple_stt(text, wait_response)
        else:
            return self._send_raw(self.user, text, wait_response)
    
    def send_multiple_stt(self, text, wait_response=False):
        for line in text.split():
            result = self._send_raw(self.user, line, wait_response)
        return result

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

if __name__ == "__main__":
    from tools.utils import setup_logging
    from config_loader import cfg

    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info('HubMessenger')
    parser = argparse.ArgumentParser(description="Hub Messenger CLI")
    parser.add_argument("-ptt", "--ptt", action="store_true")
    parser.add_argument("payload", nargs="+")

    args = parser.parse_args()
    content = " ".join(args.payload).strip()
    user = "system"
    pwd = getattr(cfg.sys.security.USERS, user, None)
    messenger = HubMessenger(user=user, password=pwd)
    if args.ptt:
        if os.path.isfile(content):
            logger.info(f"Processing audio file: {content}")
            success = messenger.send_ptt(content)
        else:
            logger.info(f"Error: File {content} not found.")
            sys.exit(1)
    else:
        text_to_send = content
        logger.info(f"Sending text message: {text_to_send}")
        success = messenger.send_stt(text_to_send, wait_response=True)

    if success:
        logger.info(f"[+] Message sent successfully. Response: {success}")
    else:
        logger.info("[!] Send failed.")
