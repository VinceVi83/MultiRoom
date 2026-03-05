__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
from Gestion import Ctes
from Gestion.Ctes import RETURN_CODE

class InterfaceSerRPIs:
    def __init__(self, ip):
        self.ip = ip
        self.port = 9999
        self.connexionRPI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Connexion etablie avec le serveur sur le port {}".format(self.port))
        self.launchConnection()

    def launchConnection(self):
        try:
            self.connexionRPI.connect((self.ip, self.port))
            return RETURN_CODE.SUCCESS
        except:
            print("Client (%s, %s) is offline")
            return RETURN_CODE.ERR_NOT_CONNECTED

    def sendMsg(self, msg):
        try:
            self.connexionRPI.send(msg.encode())
            return RETURN_CODE.SUCCESS
        except:
            print("Client (%s, %s) is offline")
            self.deconnexion()
            return RETURN_CODE.ERR_NOT_CONNECTED

    def deconnexion(self):
        print("Fermeture de la connexion")
        self.connexionRPI.close()