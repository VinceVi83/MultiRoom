__author__ = 'VinceVi83'

import os
from Gestion import Ctes



class VlControl():
    '''
    Works only on Linus OS and please install VLC on your computer
    '''

    def __init__(self, port):
        self.port = port
        self.base_cmd = 'wget --http-user=' + Ctes.user_vlc + ' --http-password=' + Ctes.pwd_vlc + ' 127.0.0.1:' + self.port + '/requests/status.xml?command_play='

    def kill_vlc(self):
        os.system('killall vlc')
        return 0

    def start_vlc(self, path):
        os.system('lancer_vlc.sh ' + self.port + ' ' + path + '&')

    def interpretation_command_vlc(self, cmd):
        """
        This function interpret the command launch the command depend of the complexity of the command
        :param cmd:
        :return:
        """
        token = len(cmd)

        if token > 1:
            self.cmd_complicated(cmd)
            return 0
        if token == 1:
            self.cmd_simple(cmd[0])
            return 0
        # Raise une erreur cela serai mieux
        return -100

    def cmd_complicated(self, cmd):
        """
        Manage to complex command as change volume, listen a repertory or sort the current playlist.
        A complex command is a command with need more than 1 argument to work
        :param command:
        :return:
        """
        if cmd[0] == 'vol':
            self.change_volume(cmd[1])
        if cmd[0] == 'dossier':
            self.change_playlist(cmd[1])
        if cmd[0] == 'sort':
            self.sort_playlist(cmd[1], cmd[2])

    def cmd_simple(self, action):
        """
        Execute the simple command to VLC
        :param action:
        :return:
        """
        cmd = self.base_cmd + action
        os.system(cmd)
        return 0

    def change_volume(self, val_volume):
        cmd = self.base_cmd + Ctes.vlc.get('vol') + val_volume
        os.system(cmd)
        return 0

    def sort_playlist(self, type_classement, ordre):
        if ordre == 0:
            cmd = self.base_cmd + Ctes.vlc.get('ordre') + type_classement
        if ordre == 1:
            cmd = self.base_cmd + Ctes.vlc.get('Rordre') + type_classement
        os.system(cmd)
        return 0

    def change_playlist(self, directory):
        cmd = self.base_cmd + Ctes.vlc.get('dossier') + directory
        os.system(cmd)
        return 0
