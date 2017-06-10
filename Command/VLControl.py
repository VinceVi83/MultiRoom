__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from Gestion import Ctes
from Gestion.Enum import *


class VlControl():
    '''
    Works only on Linus OS and please install VLC on your computer
    '''

    def __init__(self):
        self.init = False
        self.port = ""
        self.baseCMD = 'wget --http-user=' + Ctes.user_vlc + ' --http-password=' + Ctes.pwd_vlc + ' 127.0.0.1:' + self.port + '/requests/status.xml?command_play='

    def killVLC(self):
        # TODO : need to kill VLC cleanly for multi users purpose
        os.system('killall vlc')
        self.init = False
        return ReturnCode.Success

    def startVLC(self, path, port):
        # TODO : need to get the PID of new VLC client to kill it and need to check path... and if there some music files
        self.port = port
        self.init = True
        os.system('lancer_vlc.sh ' + self.port + ' ' + path + '&')
        return ReturnCode.Success

    def interpretationCommandVLC(self, cmd):
        """
        This function interpret the command launch the command depend of the complexity of the command
        :param cmd:
        :return:
        """
        token = len(cmd)

        if cmd[0] in Ctes.vlc.key():
            return ReturnCode.ErrInvalidArgument
        if token > 1:
            self.cmdComplicated(cmd)
            return ReturnCode.Success
        if token == 1:
            self.cmdSimple(cmd[0])
            return ReturnCode.Success

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
