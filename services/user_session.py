import time
import logging
from threading import Thread, Event
from services.vlc_control import VLControl
from tools.music_info import Music
from config_loader import cfg

class UserSession:
    def __init__(self, username, index):
        print(f"[*] UserSession {index} initialized")
        self.thread_info = None
        self.stop_threads = Event()
        self.linked_RPI_speakers = []
        self.username = username
        self.index = index
        self.socks = []
        self.last_seen = 0
        self.vlc = VLControl(self, self.index)
        self.music = Music(self.index)
        self.COMPLEX_CTRL = ["VLC", "PLAYLIST"]
        self.ACTION_VLC = ["next", "prev", "playlist"]
        self._start_update_info()


    def send_to_all_socks(self, text):
        for sock in self.socks:
            print("Test")
            sock.send(text.encode())

    def cmd(self, full_msg):
        """Main router for user commands."""
        if not full_msg:
            return cfg.cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

        command = full_msg.split(" ")
        print(f"[DEBUG] Session {self.index} received: {command}")

        action_target = command[0].upper()

        if action_target in self.COMPLEX_CTRL:
            if action_target == "VLC":
                return self._cmd_vlc(command[1:])
            if action_target == "PLAYLIST":
                return self._cmd_vlc(command[1:])
            if action_target == "MUSIC":
                return self._cmd_music(command[1:])

        return self.vlc.interpret_vlc_command(command)

    def _cmd_vlc(self, command):
        """Specific logic for VLC commands."""
        if not command:
            return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT
        return self.vlc.interpret_vlc_command(command)

    def _cmd_music(self, command):
        """Handles metadata and music queries."""
        if not command:
            self.music.update_status()
            return cfg.RETURN_CODE.SUCCESS

        action = command[0].lower()
        if action == "info":
            self.music.update_status()
            return self.music.get_info_json()

        return cfg.RETURN_CODE.ERR

    def stop_all_services(self):
        """Stops all services and kills the associated VLC process."""
        self.stop_threads.set()
        self.vlc.kill_vlc()
        if self.thread_info:
            self.thread_info.join(timeout=2)
            self.thread_info = None
        print(f"[*] UserSession {self.index} completely stopped.")



    def add_RPI(self, sock):
        """Adds a client socket to the broadcast list and pushes the current status."""
        if sock not in self.linked_RPI_speakers:
            self.linked_RPI_speakers.append(sock)

        if self.vlc.is_initialized:
            self.music.update_status()
            msg = self.music.get_info_json()
            if msg:
                try:
                    sock.send(msg.encode())
                except Exception as e:
                    logging.error(f"Failed to send initial info: {e}")

    def remove_RPI(self, sock):
        """Removes a client from the broadcast list."""
        if sock in self.linked_RPI_speakers:
            self.linked_RPI_speakers.remove(sock)

    def _send_broadcast(self, msg):
        """Sends a message to all active clients in the session."""
        for s in list(self.linked_RPI_speakers):
            try:
                s.send(msg.encode())
            except (BrokenPipeError, ConnectionResetError, Exception):
                self.remove_RPI(s)



    def _start_update_info(self):
        """Starts the thread to monitor VLC status."""
        self.thread_info = Thread(target=self._update_info_loop, daemon=True)
        self.thread_info.start()

    def _update_info_loop(self):
        """Monitoring loop: broadcast if the title changes or if time elapses."""
        while not self.stop_threads.is_set():
            if self.vlc.is_initialized:
                old_music = self.music.current_music
                self.music.update_status()


                if self.music.current_music != old_music:
                    self._send_broadcast(self.music.get_info_json())

            time.sleep(2)

