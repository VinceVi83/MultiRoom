"""
Service management for coordinating VLC control and music metadata broadcasting.
"""
import time
import logging
from threading import Thread, Event
from Command.VLControl import VLControl
from Gestion.Ctes import RETURN_CODE
from Gestion.Music import Music

COMPLEX_CTRL = ["VLC", "Music"]
ACTION_VLC = ["next", "prev", "playlist"]

class Service:
    def __init__(self, sock, index):
        print("Service created")
        self.thread_info = None
        self.stop_threads = Event()
        self.communication = []
        self.stream_to_ip = []
        self.index = index
        self.sock = sock
        self.vlc = VLControl(self, self.index)
        self.music = Music(self.index)

    # region Command Management
    def cmd(self, full_msg):
        """Main router for user commands."""
        command = full_msg.split(" ")
        if not command:
            return RETURN_CODE.ERR_INVALID_ARGUMENT
        print(command)
        action_target = command[0].lower()
        if action_target in ["vlc", "playlist"]:
            return self._cmd_vlc(command[1:])
        if action_target == "Music":
            return self._cmd_music(command[1:])
        
        return RETURN_CODE.ERR

    def _cmd_vlc(self, command):
        """Handles VLC specific logic."""
        return self.vlc.interpret_vlc_command(command)

    def _cmd_music(self, command):
        """Handles metadata and playlist information."""
        if not self.vlc.is_initialized:
            return RETURN_CODE.ERR
            
        cmd_type = command[0]
        if cmd_type == "info":
            print(f"Music: {self.music.current_music}")
        return RETURN_CODE.SUCCESS
    # endregion

    # region Update management
    def services_update(self):
        """Called by VLControl to force an immediate refresh of metadata."""
        self._stop_update_info()
        self._start_update_info()

    def _update_music_once(self):
        """Single fetch and broadcast of metadata."""
        if self.vlc.is_initialized:
            self.music.update_status()
            msg = self.music.get_info_json()
            if msg and self.communication:
                self._send_broadcast(msg)

    def _update_music_loop(self):
        """Monitoring loop that stops gracefully on signal."""
        while not self.stop_threads.is_set():
            vlc_ref = getattr(self, 'vlc', None)
            if vlc_ref:
                self.music.update_status()
                msg = self.music.get_info_json()
                if msg and self.communication:
                    self._send_broadcast(msg)
                
                wait_time = int(self.music.time_remaining) + 5
                for _ in range(wait_time):
                    if self.stop_threads.is_set():
                        return
                    time.sleep(1)
            else:
                time.sleep(5)

    def _start_update_info(self):
        """Starts the background monitoring loop."""
        if self.thread_info is None or not self.thread_info.is_alive():
            self.stop_threads.clear()
            self.thread_info = Thread(target=self._update_music_loop, daemon=True)
            self.thread_info.start()

    def _stop_update_info(self):
        """Safely signals and joins the background thread."""
        self.stop_threads.set()
        if self.thread_info:
            self.thread_info.join(timeout=2)
            self.thread_info = None
    # endregion

    # region Client management
    def stop_all_services(self):
        """Stops all threads and kills the VLC process."""
        self._stop_update_info()
        self.vlc.kill_vlc()
        print(f"Service {self.index} completely stopped.")
        
    def add_client(self, sock):
        """Adds a new socket to the broadcast list and sends initial state."""
        if sock not in self.communication:
            self.communication.append(sock)
            
        if self.vlc.is_initialized:
            self.music.update_status()
            msg = self.music.get_info_json()
            if msg:
                try:
                    sock.send(msg.encode())
                except Exception as e:
                    logging.error(f"Failed to send initial info: {e}")

    def remove_client(self, sock):
        """Removes a client socket safely."""
        if sock in self.communication:
            self.communication.remove(sock)

    def _send_broadcast(self, msg):
        """Broadcasts a message to all active clients of this service."""
        for s in list(self.communication):
            try:
                s.send(msg.encode())
            except (BrokenPipeError, ConnectionResetError, Exception):
                self.remove_client(s)
    # endregion