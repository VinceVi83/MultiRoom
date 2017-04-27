__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import Gestion.Ctes
from Command.VLControl import VlControl
import time
from Gestion.Enum import *
from Server.InterfaceSerRPIs import InterfaceSerRPIs

class Service:
    def __init__(self, port_local, port_stream):
        self.VLC = VlControl(port_local)
        self.port_stream = port_stream
        self.init = False
        self.path = []
        self.stream_to_ip = []

    def initVLC(self, path, ip_s):
        self.path = path
        self.ip_s = ip_s
        self.VLC.startVLC(path)
        # I hope the server don't lag
        time.sleep(10)
        self.startStream(ip_s)
        self.init = True
        return ReturnCode.Succes

    def startStream(self, ip):
        for ip in self.stream_to_ip:
            self.sendCommand('VLC.Start.' + Gestion.Ctes.local_ip + ":" + self.port_stream)
        return ReturnCode.Succes

    def stopStream(self):
        for ip in self.stream_to_ip:
            self.sendCommand('VLC.Stop')
        self.VLC.killVLC()
        return ReturnCode.Succes

    def sendCommand(self, ip, cmd):
        tmpConnection = InterfaceSerRPIs(ip)
        tmpConnection.sendMsg(cmd.encode())
        # TODO : Need to implement ack method for the execution of the command by RPI to server
        tmpConnection.deconnexion()
        return ReturnCode.Succes