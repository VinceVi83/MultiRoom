__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

pathRepPlaylist = '/'

from Gestion.Music import Music
from Gestion.Interpretation import *
from Gestion.Enum import *
import os

class ManagePlaylist():
    '''
    Library to use playlist you can create, delete a playlist.
    Add or delete a song from a playlist during the play
    Maybe later add all song contain "name" in playlist
    '''

    def __init__(self, name):
        self.currentPlaylist = pathRepPlaylist + name

    def changePlaylist(self, name):
        return ReturnCode.ErrNotImplemented

    def addSongToPlaylist(self, name, namePlaylist):
        '''
        This function permit you to add the current song to a playlist. If the playlist doesn't exist in the database so
        It will ask you if you create a playlist with the name
        :param name: name of playlist where you want add the current song
        :return:
        '''

        name = ''
        if True:
            self.addSong(name, namePlaylist)
        else:
            print(
                "Cette playliste n'existe pas dans votre base de donnée. Voulez-vous créer une nouvelle playliste " + name)
            if permissionUser().decision():
                self.createPlaylist(name)
                self.addSong(name)

    def addSong(self, name, namePlaylist=None):
        """
        Add the current song in the playlist
        TODO : multi playlist ???
        :param name: name of the playlist where you want add the current song
        :return:
        """
        # processus de musique
        if namePlaylist == None:
            pathPlaylist = self.currentPlaylist

        path = Music.path()
        nom_musique = Music.name()

        fic = open(pathPlaylist + name, 'a')
        fic.write('biduleformater + \n')
        # ~ Un petit write
        return ReturnCode.ErrNotImplemented


    def deleteSong(self, name, namePlaylist):
        """
        Delete the current song in the current playlist
        :return:
        """
        nom = self.currentPlaylist
        nom_musique = Music.name()
        fic = open(nom, 'r')
        token = ''
        text = ''
        read = ''
        while read != token:
            read = fic.readline()

            if nom_musique not in read:
                text += read

        fic.close()
        fic = open(self.currentPlaylist + nom, 'w')
        fic.write(text)
        fic.close()

    @staticmethod
    def createPlaylist(path):
        """
        Create the playlist with "name"
        :param name: name of the playlist
        :return:
        """
        os.system('cp /home/Modèle/playlist ' + path + 'extension a choisir')
        return ReturnCode.Succes

    @staticmethod
    def deletePlaylist(path):
        """
        Delete the playlist
        :param name: name of the playlist
        :return:
        """
        os.system('rm ' + path + 'extension a choisir')
        return ReturnCode.Succes
