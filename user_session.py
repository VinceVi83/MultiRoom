from threading import Event
from config_loader import cfg
import logging
logger = logging.getLogger(__name__)

class UserSession:
    """User Session Manager
    
    Role: Manages user sessions, services, and communication with connected devices.
    
    Methods:
        __init__(self, username, index) : Initialize user session with username and index.
        add_new_service(self, service_name, service) : Add a new service to the session.
        send_to_all_socks(self, text) : Send text to all connected socks.
        cleanup_services(self) : Clean up inactive services.
        stop_all_services(self) : Stop all services and clear them.
    """

    def __init__(self, username, index):
        self.thread_info = None
        self.stop_threads = Event()
        self.linked_RPI_speakers = []
        self.username = username
        self.cfg = getattr(cfg, username, None)
        self.index = index
        self.socks = []
        self.last_seen = 0
        self.services = {}

    def add_new_service(self, service_name, service):
        if not service_name or not service:
            return cfg.RETURN_CODE.INVALID_INPUT
        
        new_type = type(service)
        
        if any(isinstance(s, new_type) for s in self.services.values()):
            return cfg.RETURN_CODE.DUPLICATE
        
        if service_name in self.services:
            return cfg.RETURN_CODE.DUPLICATE

        self.services[service_name] = service
        service.attached = True
        return cfg.RETURN_CODE.SUCCESS

    def send_to_all_socks(self, text):
        if not self.socks:
            return
        
        for sock in self.socks:
            try:
                sock.send(text.encode())
            except (BrokenPipeError, ConnectionError, OSError):
                continue

    def cleanup_services(self):
        to_delete = []
        for name, service in self.services.items():
            if hasattr(service, 'is_alive'):
                try:
                    if not service.is_alive():
                        to_delete.append(name)
                except Exception:
                    to_delete.append(name)
        
        for name in to_delete:
            try:
                del self.services[name]
            except KeyError:
                pass

    def stop_all_services(self):
        for name, service in list(self.services.items()):
            if hasattr(service, 'stop'):
                service.stop()
    
        self.services.clear()
        self.stop_threads.set()
