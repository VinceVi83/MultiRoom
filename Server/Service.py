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
import re

complexCtrl = ["VLC", "Music"]
actionVLC = ["next", "prev", "dir"]

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
        self.endService = False

    #Todo use duration time to update info
    def updateInfo(self):
        while not self.stop_threads.is_set():
            if len(self.communication):
                self.updateMusic()
                # smart update, no others methods to know when vlc go to next song
                for i in range(self.music.timeRemaining):
                    if self.endService:
                        break
                    time.sleep(1)
            else:
                time.sleep(60)

    def updateMusic(self):
        if len(self.communication):
            self.music.updateInfo()
            msg = self.music.printInfo()
            # self.send("Update\n")
            if msg:
                self.send(msg)

    def addClient(self, sock):
        self.communication.append(sock)
        if self.VLC.init:
            self.music.updateInfo()
            msg = self.music.printInfo()
            if msg:
                sock.send(msg.encode())

    def stopServices(self):
        self.endService = True
        if self.VLC.init:
            self.VLC.killVLC()
            print("Wait threadInfo finish his last job")
            self.stopUpdateInfo()


    def removeClient(self, sock):
        self.communication.remove(sock)

    # Todo need to manage case stop/pause
    def actionVLC(self):
        if len(self.communication):
            self.music.updateInfo()
            msg = self.music.printInfo()
            if msg:
                self.send(msg)

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
                #self.communication.remove(s)
                #s.close()

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
            if command[0] == "start":
                command[1] = command[1].translate(str.maketrans(Ctes.escape_char))
                self.music.workingDir = command[1]
                command[0] = "dir"
            if command[0] == "kill":
                self.VLC.killVLC()
                self.stopStream()
                self.init = False
                return ReturnCode.Success
            ret = self.VLC.interpretationCommandVLC(command)
            if command[0] in actionVLC:
                self.actionVLC()
            return ret

        else:
            if len(command) < 2:
                return ReturnCode.Err

            if command[0] == "start":
                """ Need to stop/start client to restart stream audio (VLC windows restart stream after a change of song, not VLC Linux..)
                if command[0] == "play":
                    if command[0] == "play":
                        command[0] = command[0] if not self.VLC.play else "pause"
                        self.VLC.play = not self.VLC.play
                """
                command[1] = command[1].translate(str.maketrans(Ctes.escape_char))
                self.music.workingDir = command[1]
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
            if command[0] == "remove":
                print(self.music.delMusic())
            if command[0] == "modify":
                self.music.metadata(self.music.getPath(), command[1])
        return ReturnCode.Success
