__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import Gestion.Ctes
from Command.VLControl import VlControl
import time
from Gestion.Enum import *
from Server.InterfaceSerRPIs import InterfaceSerRPIs
from Gestion.Music import *

complexCtrl = ["VLC", "Music"]

class Service:
    def __init__(self, port_ctrl, port_stream):
        print("Register a new user")
        self.VLC = VlControl(port_ctrl, port_stream)
        #Todo need a function to affect port to control and stream in case of multiple instance of VLC
        self.port_ctrl = port_ctrl
        self.port_stream = port_stream
        self.init = False
        self.path = []
        self.stream_to_ip = []
        self.music = Music(port_ctrl)

    def launchStreamTo(self, ip):
        for ip in self.stream_to_ip:
            self.sendCommand(ip, 'Server/VLC/Start/' + Gestion.Ctes.local_ip + "/" + self.port_stream)
        return ReturnCode.Success

    def stopStream(self):
        for ip in self.stream_to_ip:
            self.sendCommand(ip, 'VLC.Stop')
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
        print("cmd" + str(command))

        if command[0] in complexCtrl:
            if len(command) < 2:
                print("Error, the command need at least two values")
                return ReturnCode.Err

            if command[0] == "VLC":
                print("To VLC control")
                return self.cmdVLC(command[1:])

            if command[0] == "Music":
                return self.cmdMusic(command[1:])
        else:
            print("Not Implemented")
            return ReturnCode.ErrNotImplemented

    def cmdVLC(self, command):
        if self.VLC.init:
            if command[0] == "kill":
                self.VLC.killVLC()
                self.stopStream()
                self.init = False
                return ReturnCode.Success

            self.VLC.interpretationCommandVLC(command)
            return ReturnCode.Success

        else:
            if len(command) < 2:
                return ReturnCode.Err

            if command[0] == "start":
                self.VLC.startVLC(command[1])
                return ReturnCode.Success
            print("VLC not initialized")
            return ReturnCode.Err

    def cmdMusic(self, command):
        if self.VLC.init:
            if command[0] == "info":
                print("Name music :" + self.music.getNameMusic() + " Path :" + self.music.getPath())

            if command[0] == "name":
                print(self.music.getNameMusic())

            if command[0] == "path":
                print(self.music.getPath())

        return ReturnCode.Success