__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import Gestion.Ctes
from Command.VLControl import VlControl
import time
from Gestion.Enum import *
from Server.InterfaceSerRPIs import InterfaceSerRPIs
from Gestion.Music import *
from threading import *

complexCtrl = ["VLC", "Music"]

class Service:
    def __init__(self, port_ctrl, port_stream):
        print("Register a new user")
        self.VLC = VlControl(self, port_ctrl, port_stream)
        #Todo need a function to affect port to control and stream in case of multiple instance of VLC
        self.port_ctrl = port_ctrl
        self.port_stream = port_stream
        self.init = False
        self.path = []
        self.communication = []
        self.stream_to_ip = []
        self.music = Music(port_ctrl)
        self.threadInfo = None
        self.stop_threads = Event()

    #Todo use duration time to update info
    def updateInfo(self):
        while not self.stop_threads.is_set():
            if len(self.communication):
                self.music.updateInfo()
                msg = self.music.printInfo()
                if msg:
                    self.send(msg)
                    # smart update, no others methods to know when vlc go to next song
                    time.sleep(self.music.timeRemaining)
                time.sleep(5)
            else:
                time.sleep(60)

    def startUpdateInfo(self):
        print("startUpdateInfo")
        self.stop_threads.clear()
        self.threadInfo = Thread(target = self.updateInfo)
        self.threadInfo.start()

    def stopUpdateInfo(self):
        self.stop_threads.set()
        self.threadInfo.join()
        self.threadInfo = None

    def launchStreamTo(self, ip):
        for ip in self.stream_to_ip:
            self.sendCommand(ip, 'Server/VLC/Start/' + Gestion.Ctes.local_ip + "/" + self.port_stream)
        return ReturnCode.Success

    def stopStream(self):
        for ip in self.stream_to_ip:
            self.sendCommand(ip, 'VLC.Stop')
        self.VLC.killVLC()
        return ReturnCode.Success

    def send(self, msg):
        for s in self.communication:
            try:
                s.send(msg.encode())
            except:
                print("Print socket dead ?")
                self.communication.remove(s)
                s.close()

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
