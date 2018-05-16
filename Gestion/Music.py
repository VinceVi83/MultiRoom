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
os.chdir("/tmp")

logging.basicConfig(filename='removed.log',level=logging.DEBUG)


# chemin = '/home/shirekan/PycharmProjects/MultiRoom/status.xml'

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

    def resetMetadata(self):
        self.metadata = {}
        self.metadata["title"] = ""
        self.metadata["artist"] = ""
        self.metadata["genre"] = ""
        self.metadata["album"] = ""
        self.metadata["comment"] = ""
        self.metadata["langage"] = ""
        self.metadata["circle"] = ""
        self.metadata["filename"] = ""

    def updateMetadata(self, pathCurrentSong):
        self.resetMetadata()
        try:
            metadata = ID3(pathCurrentSong)
        except:
            metadata = mutagen.File(pathCurrentSong, easy=True)
            print("Exception updateMetadata")

        """
        >>> tag["COMM"].text
        ['This is comment!']
        """
        for key in metadata.keys():
            if key in Ctes.mutagen_keys.keys():
                self.metadata[Ctes.mutagen_keys[key]] = metadata[key].text[0]

    def modifyMetadata(self, pathCurrentSong, metadataModified):
        self.resetMetadata()
        try:
            metadata = ID3(pathCurrentSong)
        except:
            metadata = mutagen.File(pathCurrentSong, easy=True)
            print("Exception updateMetadata")

        listdata = metadataModified.split("\n")
        metadataDico = {}
        for data in listdata:
            tmp = data.split("==")
            metadataDico[tmp[0]] = tmp[1]

        for key in metadata.keys():
            if key not in metadataDico.keys():
                self.registerKey(key, metadataDico[key])

            if key in Ctes.mutagen_keys.keys():
                if metadata[key].text[0] != metadataDico[Ctes.mutagen_keys[key]]:
                    metadata[key].text[0] = metadataDico[Ctes.mutagen_keys[key]]
        metadata.save()
        return ReturnCode.Success

    def registerKey(self, key, value):
        if key is "filename":
            print("Change filename")
        print("Key not exit in file" + key + value)

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
        self.workingDir = ""

    def updateInfo(self):
        returnCode = self.getNameMusic()
        if returnCode is ReturnCode.Err:
            print("VLC problem")
            return ReturnCode.Err
        self.currentMusic = returnCode
        path = self.getPath()
        if path is "":
            return ReturnCode.Err
        dir = os.path.dirname(path)
        if self.currentDir is not dir:
            self.lastDir = self.currentDir
            self.currentDir = dir
        self.metadata.updateMetadata(path)
        return ReturnCode.Success

    def printInfo(self):
        msg = "metadata:"
        if self.currentMusic is "":
            return ReturnCode.Err
        if self.metadata.metadata["title"] is "":
            self.metadata.metadata["title"] = self.currentMusic
        self.metadata.metadata["filename"] = self.currentMusic
        for k, v in self.metadata.metadata.items():
            msg += k + "==" + v + "\n"
        return msg

    def getNameMusic(self):
        """
        Retrieve the name of the current song play in VLC
        :return:
        """
        try:
            if os.path.isfile("/tmp/status.xml"):
                os.system('rm /tmp/status.xml*')
            os.system(self.cmd)
            print(self.cmd)
            tree = ET.parse("/tmp/status.xml")
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
        path = self.getPath()
        logging.warning("delMusic called --> mv " + path + " " + Ctes.trash)
        if path is "":
            return ReturnCode.Err
        os.system("mv " + path + " " + Ctes.trash)

        '''
        logging.warning("delMusic called --> rm " + path + " " + trash)
        os.system("rm " + path + " " + trash)
        '''
        return ReturnCode.Success

    def checkedMusic(self):
        """
        Need to change in all playlist also....
        :return:
        """
        path = self.getPath()
        logging.warning("delMusic called --> mv " + path + " " + Ctes.check)
        if path is "":
            return ReturnCode.Err
        os.system("mv " + path + " " + Ctes.check)
        return ReturnCode.Success

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
            for v in p:
                currentPath = v.decode().split("/")
                if self.currentMusic in currentPath[-1]:
                    path = v.decode()
                    break
            if path is not '':
                return path
            return ""
        except:
            print('Exception : File Not Found')
            self.maj_db()
            self.count = self.count + 1
            if self.count > 3:
                print(self.currentMusic)
                return ""
            return self.getPath()

    def maj_db(self):
        """
        Update the database witch record all files with their path in a file in binary
        :return:
        """
        os.system('echo ' + Ctes.pwd_linux + ' |  sudo -S updatedb -o external.red.db -U ' + self.workingDir)
