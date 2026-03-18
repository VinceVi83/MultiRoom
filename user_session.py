import time
import logging
from threading import Thread, Event
from config_loader import cfg


class UserSession:
    """Manages user sessions, handling commands and broadcasting updates.

    Methods:
        __init__(username, index) : Initializes the user session.
        send_to_all_socks(sockets) : Sends a message to all connected sockets.
        cmd(full_msg) : Routes user commands.
        _cmd_vlc(command) : Handles VLC-related commands.
        _cmd_music(command) : Handles music-related commands.
        stop_all_services() : Stops all services and kills the VLC process.
        add_RPI(sock) : Adds a client socket to the broadcast list.
        remove_RPI(sock) : Removes a client socket from the broadcast list.
        _send_broadcast(msg) : Sends a message to all active clients.
        _start_update_info() : Starts a thread to monitor VLC status.
        _update_info_loop() : Monitoring loop to broadcast updates.
    """

    def __init__(self, username, index):
        self.thread_info = None
        self.stop_threads = Event()
        self.linked_RPI_speakers = []
        self.username = username
        self.index = index
        self.socks = []
        self.last_seen = 0
        self.services = {}

    def add_new_service(self, service_name, service):
        nouveau_type = type(service)
        
        if any(isinstance(s, nouveau_type) for s in self.services.values()):
            print(f"Refusé : Un service de type {nouveau_type.__name__} est déjà présent.")
            return cfg.RETURN_CODE.DUPLICATE
        
        if service_name in self.services:
            print(f"Refusé : Le nom '{service_name}' est déjà utilisé.")
            return cfg.RETURN_CODE.DUPLICATE

        self.services[service_name] = service
        service.attached = True
        return cfg.RETURN_CODE.SUCCESS

    def send_to_all_socks(self, text):
        for sock in self.socks:
            sock.send(text.encode())
