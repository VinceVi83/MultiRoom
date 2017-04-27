__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
from Gestion.Enum import *

class InterfaceSerRPIs:
    def __init__(self, ip):
        self.ip = ip
        self.port = 8888
        self.connexionRPI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Connexion etablie avec le serveur sur le port {}".format(self.port))
        self.launchConnection()

    def launchConnection(self):
        try:
            self.connexionRPI.connect((self.ip, self.port))
            return ReturnCode.Succes
        except:
            print("Client (%s, %s) is offline")
            return ReturnCode.ErrNotConnected

    def sendMsg(self, msg):
        try:
            self.connexionRPI.send(msg.encode())
            return ReturnCode.Succes
        except:
            print("Client (%s, %s) is offline")
            self.deconnexion()
            return ReturnCode.ErrNotConnected

    def deconnexion(self):
        print("Fermeture de la connexion")
        self.connexionRPI.close()