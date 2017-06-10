__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import Gestion.Ctes
from Command.VLControl import VlControl
import time
from Gestion.Enum import *
from Server.InterfaceSerRPIs import InterfaceSerRPIs

class Service:
    def __init__(self):
        print("Register a new user")
        self.VLC = VlControl()
        #Todo need a function to affect port to control and stream in case of multiple instance of VLC
        self.port_ctrl = "8080"
        self.port_stream = "9000"
        self.init = False
        self.path = []
        self.stream_to_ip = []

    def initVLC(self, path, ip_s):
        self.VLC = VlControl()
        self.path = path
        self.ip_s = ip_s
        self.VLC.startVLC(path, self.port_ctrl)
        # I hope the server doesn't lag
        time.sleep(10)
        self.startStream(ip_s)
        self.init = True
        return ReturnCode.Success

    def startStream(self, ip):
        for ip in self.stream_to_ip:
            self.sendCommand('VLC.Start.' + Gestion.Ctes.local_ip + ":" + self.port_stream)
        return ReturnCode.Success

    def stopStream(self):
        for ip in self.stream_to_ip:
            self.sendCommand('VLC.Stop')
        self.VLC.killVLC()
        return ReturnCode.Success

    def sendCommand(self, ip, cmd):
        tmpConnection = InterfaceSerRPIs(ip)
        tmpConnection.sendMsg(cmd.encode())
        # TODO : Need to implement ack method for the execution of the command by RPI to server
        tmpConnection.deconnexion()
        return ReturnCode.Success

    def cmd(self, command):
        # Example application.commande
        if command[0] is "VLC":
            if not self.init:
                self.initVLC(command[1], command[2:])
                return ReturnCode.Success

        if len(command) < 2:
            print("Error")
            return ReturnCode.Err

        if command[1] is "kill":
            self.VLC.killVLC()
            self.stopStream()
            return ReturnCode.Success

        if self.VLC.init:
            self.VLC.interpretationCommandVLC(command[1:])
            return ReturnCode.Success
        else:
            print("VLC not initialized")

