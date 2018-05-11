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
        # Todo need to manage the end of playlist to remove lop, if not the vlc clients will try to connect until it restart..
        self.processus = ""
        self.portCtrl = str(portCtrl)
        self.portStream = str(portStream)
        self.path = ""
        # To start/stop threadInfo
        self.services = services
        self.vlc_opts = " --http-port=" + self.portCtrl + " --sout \"#standard{access=http,mux=ogg,dst=" + Ctes.local_ip + ":" + self.portStream + "}\"" + " -I dummy" + " --loop"
        print(self.vlc_opts)
        self.baseCMD = 'wget --http-user=' + Ctes.user_vlc + ' --http-password=' + Ctes.pwd_vlc + ' ' + ' ' + Ctes.local_ip + ':' + self.portCtrl + '/requests/status.xml?command='
        print(self.baseCMD)

    def killVLC(self):
        # TODO : need to kill VLC cleanly for multi users purpose
        if self.processus:
            self.processus.terminate()
            self.init = False
            self.port = 0
            self.path = ""
        return ReturnCode.Success

    def startVLC(self, path):
        # TODO : need to get the PID of new VLC client to kill it and need to check path... and if there some music files
        self.init = True
        self.path = path
        self.services.startUpdateInfo()
        cmd = "vlc " + self.path + self.vlc_opts
        return ReturnCode.Err
        #self.processus = Popen(cmd, shell=True)
        #return ReturnCode.Success

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
        if cmd[0] == 'dossier':
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

        cmd = self.baseCMD + Ctes.vlc[action]
        os.system(cmd)

        return ReturnCode.Success

    def changeVolume(self, valVolume):
        cmd = self.baseCMD + Ctes.vlc['vol'] + valVolume
        print("print wget" + cmd)
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
        cmd = self.baseCMD + Ctes.vlc['dossier'] + directory
        os.system(cmd)
        return ReturnCode.Success
