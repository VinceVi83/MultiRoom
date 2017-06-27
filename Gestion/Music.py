__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import re
from Gestion import Ctes
from Gestion.Enum import *
import xml.etree.cElementTree as ET
from pathlib import Path

path = ''
pwd_vlc = ''
chemin = '/run/media/vinsento/455B532D7757A5FD/Project/MultiRoom/status.xml'
user_vlc = ''

class MusicMetadata:

    def __init__(self):
        self.artist = ""
        self.album = ""

    def updateMetadata(self, pathCurrentSong):
        return ReturnCode.ErrNotImplemented

class Music():
    '''
    Library about a function link with a current song
    Works only on Linus OS
    '''

    def __init__(self, portCtrl):
        self.currentMusic = ""
        self.path = ""
        self.metadata = MusicMetadata()
        self.portCtrl = str(portCtrl)
        self.count = 0
        self.cmd = 'wget --http-user=' + Ctes.user_vlc + ' --http-password=' + Ctes.pwd_vlc + ' ' + ' ' + Ctes.local_ip + ':' + self.portCtrl + '/requests/status.xml'

    def updateInfo(self):
        self.currentMusic = self.getNameMusic()
        self.path = self.getPath()


    def getNameMusic(self):
        """
        Retrieve the name of the current song play in VLC
        :return:
        """
        try:
            if os.path.isfile(chemin):
                os.system('rm status.xml')
            os.system(self.cmd)
            print(self.cmd)


            if not os.path.isfile(chemin):
                return ReturnCode.ErrNotImplemented

            tree = ET.parse(chemin)
            root = tree.getroot()
            nodeInformation = root.find("information")
            for nodeInfo in nodeInformation[0]:
                if nodeInfo.attrib["name"] == "filename":
                    self.currentMusic = nodeInfo.text
                    return nodeInfo.text


        except:
            print('File Not Found or VLC is not running')
        return "toto"


    def delMusic(self):
        """
        Need to delete in all playlist also....
        :return:
        """
        return ReturnCode.ErrNotImplemented

    def getPath(self):
        """
        Retrieve the path of the current song play in VLC from database contained all path of all files in the system
        :return:
        """

        try:
            p = subprocess.check_output(["locate", self.currentMusic, "--database", "external.red.db"])
            p = p.splitlines()
            path = ''
            # v.decode() car le fichier est en binaire va savoir pourquoi...Flem de lire la doc
            for v in p:
                currentPath = v.decode().split("/")
                if self.currentMusic in currentPath[-1]:
                    # Cela serai bien de trouver des doublons
                    # Avec un test regex pour le chemin
                    path = v.decode()
                    break
            # Raise une erreur cela serai mieux
            if path is not '':
                return path
            return 'Probleme'
        except:
            print('Exception : File Not Found')
            Music.maj_db()
            self.count = self.count + 1
            if self.count > 5:
                print(self.currentMusic)
                return "Error"
            self.getPath()

    @staticmethod
    def maj_db():
        """
        Update the database witch record all files with their path in a file in binary
        :return:
        """
        os.system('sudo updatedb -o external.red.db -U /run/media/vinsento/455B532D7757A5FD/Project/Test/')



    def modifyMetaData(self):
        return ReturnCode.ErrNotImplemented

