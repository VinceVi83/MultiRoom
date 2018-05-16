__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from Gestion import Ctes
from Gestion.Enum import *
from subprocess import *

import time

class VlControl():
    '''
    Works only on Linus OS and please install VLC on your computer
    '''

    def __init__(self, services, portCtrl, portStream):
        self.init = False
        self.process = Popen
        self.play = False
        self.portCtrl = str(portCtrl)
        self.portStream = str(portStream)
        self.path = ""
        # To start/stop threadInfo
        self.services = services
        self.vlc_opts = " --http-port=" + self.portCtrl + " --sout \"#standard{access=http,mux=ogg,dst=" + Ctes.local_ip + ":" + self.portStream + "}\"" + " -I dummy"#  + " --loop"
        self.baseCMD = 'curl --user :' + Ctes.pwd_vlc + ' ' + ' ' + Ctes.local_ip + ':' + self.portCtrl + '/requests/status.xml?command='

    def killVLC(self):
        if self.process:
            os.system("kill -9 " + str(self.process.pid))
            self.init = False
            self.play = False
            self.path = ""
        return ReturnCode.Success

    def startVLC(self, path):
        self.init = True
        self.play = True
        self.path = path
        cmd = "vlc " + self.path + self.vlc_opts
        self.process = Popen(cmd, shell=True)

        self.services.startUpdateInfo()
        return ReturnCode.Success

    def interpretationCommandVLC(self, cmd):
        """
        This function interpret the command launch the command depend of the complexity of the command
        :param cmd:
        :return:
        """
        token = len(cmd)
        print("interpretationCommandVLC " + str(cmd))
        print(Ctes.vlc.keys())
        if not cmd[0] in Ctes.vlc.keys():
            print("Argument inconnu")
            return ReturnCode.ErrInvalidArgument
        if token > 1:
            self.cmdComplicated(cmd)
            return ReturnCode.Success
        if token == 1:
            self.cmdSimple(cmd[0])
            return ReturnCode.Success
        return ReturnCode.Err

    def cmdComplicated(self, cmd):
        """
        Manage to complex command as change volume, listen a repertory or sort the current playlist.
        A complex command is a command with need more than 1 argument to work
        :param command:
        :return:
        """
        if cmd[0] == 'vol':
            self.changeVolume(cmd[1])
            return ReturnCode.Success
        if cmd[0] == 'dir':
            self.changePlaylist(cmd[1])
            return ReturnCode.Success
        if cmd[0] == 'sort':
            self.sortPlaylist(cmd[1], cmd[2])
            return ReturnCode.Success
        return ReturnCode.ErrInvalidArgument

    def cmdSimple(self, action):
        """
        Execute the simple command to VLC
        :param action:
        :return:
        """

        cmd = self.baseCMD + Ctes.vlc[action] + " > /dev/null"
        os.system(cmd)
        return ReturnCode.Success

    def changeVolume(self, valVolume):
        cmd = self.baseCMD + Ctes.vlc['vol'] + valVolume
        os.system(cmd)
        return ReturnCode.Success

    def sortPlaylist(self, typeClassement, ordre):
        cmd = ""
        if ordre == 0:
            cmd = self.baseCMD + Ctes.vlc['order'] + typeClassement
        if ordre == 1:
            cmd = self.baseCMD + Ctes.vlc['Rordre'] + typeClassement
        if cmd == "":
            return ReturnCode.ErrInvalidArgument
        os.system(cmd)
        return ReturnCode.Success


    def changePlaylist(self, directory):
        cmd = self.baseCMD + Ctes.vlc['dir'] + directory + " > /dev/null"
        os.system(cmd)
        return ReturnCode.Success
