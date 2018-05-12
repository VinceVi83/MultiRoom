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
import logging
import pprint
import mutagen
from mutagen.id3 import ID3, COMM

#audio.add(COMM(encoding=3, text=u"This is comment!"))
#audio.save()

logging.basicConfig(filename='removed.log',level=logging.DEBUG)

#Todo add to Ctes.py
chemin = '/home/shirekan/PycharmProjects/MultiRoom/status.xml'
trash = "/NAS/Music/Trash/"
checked = "/NAS/Music/Check/"

# Mutagen
class MusicMetadata:

    def __init__(self):
        self.metadata = {}
        self.metadata["title"] = ""
        self.metadata["artist"] = ""
        self.metadata["genre"] = ""
        self.metadata["album"] = ""
        self.metadata["comment"] = ""
        self.metadata["langage"] = ""
        self.metadata["circle"] = ""
        """
        mutagen_keys['TCOM'] = 'title'
        mutagen_keys['TPE1'] = 'artist'
        mutagen_keys['TALB'] = 'album'
        mutagen_keys['TPE2'] = 'circle'
        mutagen_keys['TCON'] = 'genre'
        mutagen_keys['COMM::XXX'] = 'comment'
        mutagen_keys['TLAN'] = 'langage'
        """
    def updateMetadata(self, pathCurrentSong):
        try:
            metadata = ID3(pathCurrentSong)
        except:
            metadata = mutagen.File(pathCurrentSong, easy=True)
            print("Exception updateMetadata")

        """
        >>> tag["COMM::XXX"].text
        ['This is comment!']
        """
        for key in metadata.keys():
            if key in Ctes.mutagen_keys.keys():
                self.metadata[Ctes.mutagen_keys[key]] = metadata[key].text[0]

    def modifyMetadata(self, pathCurrentSong, metadata):
        return ReturnCode.ErrNotImplemented

class Music():
    '''
    Library about a function link with a current song
    Works only on Linus OS
    '''

    def __init__(self, portCtrl):
        self.currentMusic = ""
        self.currentDir = ""
        self.lastDir = ""
        self.metadata = MusicMetadata()
        self.portCtrl = str(portCtrl)
        self.count = 0
        self.cmd = 'wget --http-user=' + Ctes.user_vlc + ' --http-password=' + Ctes.pwd_vlc + ' ' + ' ' + Ctes.local_ip + ':' + self.portCtrl + '/requests/status.xml'
        self.countFail = 0
        self.timeRemaining = 5

    def updateInfo(self):
        returnCode = self.getNameMusic()
        if returnCode is ReturnCode.Err:
            print("VLC problem")
            return ReturnCode.Err
        self.currentMusic = returnCode
        path = self.getPath()
        dir = os.path.dirname(path)
        if self.currentDir is not dir:
            self.lastDir = self.currentDir
            self.currentDir = dir
        self.metadata.updateMetadata(path)

    def printInfo(self):
        msg = "metadata:"
        if self.currentMusic is "":
            return
        if self.metadata.metadata["title"] is "":
            self.metadata.metadata["title"] = self.currentMusic

        for k, v in self.metadata.metadata.items():
            msg += k + "==" + v + "\n"
        return msg

    def getNameMusic(self):
        """
        Retrieve the name of the current song play in VLC
        :return:
        """
        try:
            if os.path.isfile(chemin):
                os.system('rm status.xml*')

            os.system(self.cmd)
            print(self.cmd)
            tree = ET.parse(chemin)
            root = tree.getroot()
            length = root.find("length").text
            timeElapse = root.find("time").text

            self.timeRemaining = int(length) - int(timeElapse)
            nodeInformation = root.find("information")
            for nodeInfo in nodeInformation[0]:
                if nodeInfo.attrib["name"] == "filename":
                    return nodeInfo.text
        except:
            print('File Not Found or VLC is not running')
        return ReturnCode.Err

    def delMusic(self):
        """
        Need to delete in all playlist also....
        :return:
        """
        logging.warning("delMusic called --> mv " + self.getPath() + " " + trash)
        os.system("mv " + self.getPath() + " " + trash)

        '''
        logging.warning("delMusic called --> rm " + self.getPath() + " " + trash)
        os.system("rm " + self.getPath() + " " + trash)
        '''
        return ReturnCode.Succes

    def getPath(self):
        """
        Retrieve the path of the current song play in VLC from database contained all path of all files in the system
        Will be use for remove a song, add/delete song from playlist
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
            return 'Problem'
        except:
            print('Exception : File Not Found')
            Music.maj_db()
            self.count = self.count + 1
            if self.count > 3:
                print(self.currentMusic)
                return "Error"
            self.getPath()

    @staticmethod
    def maj_db():
        """
        Update the database witch record all files with their path in a file in binary
        :return:
        """
        os.system('echo ' + Ctes.pwd_linux + ' |  sudo -S updatedb -o external.red.db -U /home/shirekan/PycharmProjects/MultiRoom/test/')
