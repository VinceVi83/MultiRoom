__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

pathRepPlaylist = "/"
pathTemplatePlaylist = "/"

from Gestion.Music import Music
from Gestion.Interpretation import *
from Gestion.Enum import *
import os
import xml.etree.cElementTree as ET
from pathlib import Path

ext = ".xspf"

class ManagePlaylist():
    '''
    Library to use playlist you can create, delete a playlist.
    Add or delete a song from a playlist during the play
    Maybe later add all song contain "name" in playlist
    '''

    def __init__(self):
        self.currentPlaylist = ""

    def changePlaylist(self, name):
        self.currentPlaylist = name
        return ReturnCode.Success

    def addSongToPlaylist(self, name,  namePlaylist=None):
        '''
        This function permit you to add the current song to a playlist. If the playlist doesn't exist in the database so
        It will ask you if you create a playlist with the name
        :param name: name of playlist where you want add the current song
        :return:
        '''

        if namePlaylist == None:
            if self.currentPlaylist:
                return ReturnCode.ErrNotImplemented
            namePlaylist = self.currentPlaylist

        if Path(pathRepPlaylist + namePlaylist):
            self.addSong(name, namePlaylist)
        else:
            self.createPlaylist(namePlaylist)
            self.addSong(name, namePlaylist)

    def addSong(self, music, namePlaylist):
        """
        Add the current song in the playlist
        :param name: name of the playlist where you want add the current song
        :return:
        """

        if not os.path.isfile(namePlaylist):
            return ReturnCode.ErrNotImplemented

        tree = ET.parse(pathRepPlaylist + namePlaylist)
        root = tree.getroot()

        nodeTracklist = root.find("trackList")

        nodeTrack = ET.SubElement(nodeTracklist, "track")
        ET.SubElement(nodeTrack, "location").text = music.path
        ET.SubElement(nodeTrack, "title").text = music.currentMusic

        newXML = ET.tostring(root)
        with open('create_users_multi_browser.xml', 'w') as f:
            f.write(newXML)

        return ReturnCode.ErrNotImplemented

    def deleteSong(self, name, namePlaylist):
        """
        Delete the current song in the current playlist
        :return:
        """
        tree = ET.parse(pathRepPlaylist + namePlaylist)
        root = tree.getroot()
        nodetrackList = root.find("trackList")

        founded = False
        for nodetrack in nodetrackList:
            for node in nodetrack:
                if node.tag is "title":
                    founded = node.text is name
            if founded:
                break

        newXML = ET.tostring(tree)
        with open('create_users_multi_browser.xml', 'w') as f:
            f.write(newXML)

    @staticmethod
    def createPlaylist(name):
        """
        Create the playlist with "name"
        :param name: name of the playlist
        :return:
        """
        os.system(pathTemplatePlaylist + name + ext)
        return ReturnCode.Success

    @staticmethod
    def deletePlaylist(name):
        """
        Delete the playlist
        :param name: name of the playlist
        :return:
        """
        os.system('rm ' + pathRepPlaylist + name + ext)
        return ReturnCode.Success
