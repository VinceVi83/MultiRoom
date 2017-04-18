__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import Gestion.Ctes
from Command.VLControl import VlControl
import time

class Service:
    def __init__(self, port_local, port_stream):
        self.VLC = VlControl(port_local)
        self.port_stream = port_stream
        self.init = False
        self.path = []
        self.stream_to_ip = []

    def init_vlc(self, path, ip_s):
        self.path = path
        self.ip_s = ip_s
        self.VLC.start_vlc(path)
        time.sleep(10)
        self.start_stream(ip_s)
        self.init = True

    def start_stream(self, ip):
        for ip in self.stream_to_ip:
            self.sendCommand('VLC.Start.' + Gestion.Ctes.local_ip + ":" + self.port_stream)

    def stop_stream(self):
        for ip in self.stream_to_ip:
            self.sendCommand('VLC.Stop')
        self.VLC.kill_vlc()

    def sendCommand(self, ip, cmd):
        port = 8888
        connexion_RPI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connexion_RPI.connect((ip, port))

        connexion_RPI.send(cmd.encode())
        connexion_RPI.close()