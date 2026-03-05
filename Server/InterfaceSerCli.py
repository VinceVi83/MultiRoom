"""
Session manager for handling multiple user connections and VLC services.
"""
import socket
import select
import threading
import logging
import time
from Gestion import Ctes
from Gestion.Ctes import RETURN_CODE
from Server import Service


class SessionManager:
    """Manages multi-user VLC sessions and network port allocation."""
    
    def __init__(self, host=Ctes.local_ip, port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.connection_list = []
        self.active_users = {}
        
        # Port Range Configuration
        self.base_ctrl_port = 9000
        self.base_stream_port = 19000
        threading.Thread(target=self._cleanup_inactive_sessions, daemon=True).start()

    def _cleanup_inactive_sessions(self):
        """Kills services for users disconnected for more than 2 hours."""
        while True:
            time.sleep(300)  # Check every 5 minutes
            now = time.time()
            to_delete = []
            
            for username, session in list(self.active_users.items()):
                last_seen = session.get('last_seen')
                if last_seen and (now - last_seen > 7200):  # 7200s = 2h
                    print(f"[*] Timeout: Automatic service removal for {username}")
                    session['service'].stop_all_services()
                    to_delete.append(username)
            
            for username in to_delete:
                del self.active_users[username]

    def _handle_client_data(self, sock):
        try:
            data = sock.recv(4096)
            if not data:
                self._mark_user_detached(sock, "clean")
                self._close_socket(sock)
                return
            
            msg = data.decode().strip()
            parts = msg.split(";")
            if len(parts) < 2:
                return

            username, payload = parts[0], parts[1]

            if username not in self.active_users:
                if self._authenticate_user(sock, username, payload):
                    print(f"[*] {username} connected.")
            else:
                session = self.active_users[username]
                if session['last_seen'] is not None:
                    print(f"[*] {username} reconnected. Timeout cancelled.")
                    session['last_seen'] = None
                    session['service'].sock = sock
                    sock.send("Connected".encode())
                
                self._manage_session(sock, username, payload)

        except Exception as e:
            print(f"Client data error: {e}")
            self._mark_user_detached(sock, "error")
            self._close_socket(sock)

    def _execute_async_command(self, user_service, full_msg):
        """Executes a service command in a background thread."""
        print(f"Executing async: {full_msg}")
        try:
            user_service.cmd(full_msg)
        except Exception as e:
            logging.error(f"Background command failed: {e}")

    # region Server management
    def start(self):
        """Initializes the master server socket."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.server_socket.bind(("0.0.0.0", self.port))
        self.server_socket.listen(10)
        self.server_socket.setblocking(False) 
        
        self.connection_list = [self.server_socket]
        print(f"[*] Master Server listening on port {self.port}...")
        self._run_loop()

    def stop_all_services(self):
        """Closes all active user services and VLC instances."""
        print("[*] Closing all active VLC services...")
        for username, user_service in self.active_users.items():
            print(f" -> Closing for {username}")
            user_service.stop_all_services()
        print("[*] Cleanup finished.")

    def _run_loop(self):
        """Main server loop using select for non-blocking I/O."""
        try:
            while True:
                readable, _, _ = select.select(self.connection_list, [], [], 0.5)
                
                for sock in readable:
                    if sock is self.server_socket:
                        try:
                            client_sock, addr = self.server_socket.accept()
                            client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                            print(f"[*] INCOMING CONNECTION: {addr}")
                            client_sock.setblocking(False)
                            self.connection_list.append(client_sock)
                        except BlockingIOError:
                            continue
                    else:
                        self._handle_client_data(sock)
        except KeyboardInterrupt:
            print("\n[*] Master Server shutdown detected...")
            self.stop_all_services()

    def _manage_session(self, sock, username, payload):
        """Routes logic and handles persistence or command execution."""
        session = self.active_users[username]
        
        if 'end' in payload:
            self._handle_disconnection(sock, username)
        else:
            # Lancement de la commande en thread séparé (PEP 8: naming arguments)
            threading.Thread(
                target=self._execute_async_command, 
                args=(session['service'], payload),
                daemon=True
            ).start()
    # endregion

    # region Authentication management
    def _authenticate_user(self, sock, username, password):
        """Handles initial connection and service allocation."""
        if username not in Ctes.USERS or password != Ctes.USERS[username]:
            print(f"Authentication failed for: {username}")
            sock.send("Denied".encode())
            self._close_socket(sock)
            return False
            
        print(f"Authentication successful: {username}")
        if username in self.active_users:
            session = self.active_users[username]
            session['last_seen'] = None
            user_service = session['service']
            user_service.sock = sock
        else:
            idx = len(self.active_users)
            user_service = Service.Service(sock, idx)
            self.active_users[username] = {'service': user_service, 'last_seen': None}
            user_service.sock = sock

        sock.send("Connected".encode())
        return True

    def _handle_disconnection(self, sock, username):
        """Handles socket closure and optional service termination."""
        # Immediate cleanup and service termination
        if username in self.active_users:
            session = self.active_users[username]
            session['service'].stop_all_services()
            del self.active_users[username]
        
        if sock:
            self._close_socket(sock)

    def _close_socket(self, sock):
        """Safely removes and closes a socket."""
        if sock in self.connection_list:
            self.connection_list.remove(sock)
        sock.close()

    def _mark_user_detached(self, sock, reason="error"):
        for name, session in self.active_users.items():
            if getattr(session['service'], 'sock', None) == sock:
                print(f"[*] {name} detached ({reason}). Service maintained for 2h.")
                session['last_seen'] = time.time()
                break
    # endregion