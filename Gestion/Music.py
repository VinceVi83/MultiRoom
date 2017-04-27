__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import re
from Gestion import Ctes
from Gestion.Enum import *

path = ''
pwd_vlc = ''
chemin = ''
user_vlc = ''

class Music():
    '''
    Library about a function link with a current song
    Works only on Linus OS
    '''

    @staticmethod
    def name():
        """
        Retrieve the name of the current song play in VLC
        :return:
        """
        try:
            os.system('wget http://127.0.0.1:8080/requests/status.xml --http-user=' + Ctes.user_vlc + ' --http-password=' + Ctes.pwd_vlc)
            file = open(chemin, 'r')
            a = file.read()
            # print(a)  a=re.search(r'a','fdfdffdabavfgfgf' test)

            pos_rep1 = re.search(r"<info name=>", a)
            debut = pos_rep1.span()[1]
            pos_rep2 = re.search(r"mp3", a)
            fin = pos_rep2.span()[1]
            os.system('rm status.xml')
            return a[debut:fin]
        except:
            print('File Not Found or VLC is not running')
        return

    @staticmethod
    def delMusic():
        return ReturnCode.ErrNotImplemented

    @staticmethod
    def path():
        """
        Retrieve the path of the current song play in VLC from database contained all path of all files in the system
        :return:
        """
        nom = Music.name()
        try:
            p = subprocess.check_output(["locate", nom, "--database", "external.red.db"])
            p = p.splitlines()
            path = ''
            # v.decode() car le fichier est en binaire va savoir pourquoi...Flem de lire la doc
            for v in p:
                if nom in v.decode():
                    # Cela serai bien de trouver des doublons
                    # Avec un test regex pour le chemin
                    path = v.decode()
            # Raise une erreur cela serai mieux
            if path is not '':
                return path
            return 'Probleme'
        except:
            print('Exception : File Not Found')
            Music.maj_db()
            Music.path()

    @staticmethod
    def maj_db():
        """
        Update the database witch record all files with their path in a file in binary
        :return:
        """
        os.system('sudo updatedb -o external.red.db -U /mnt/NAS/')
