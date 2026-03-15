import socket
from Gestion import Ctes
from Gestion.Ctes import RETURN_CODE

class InterfaceSerRPIs:
    def __init__(self, ip):
        self.ip = ip
        self.port = 9999
        self.connexionRPI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Connection established with the server on port {}".format(self.port))
        self.launchConnection()

    def launchConnection(self):
        try:
            self.connexionRPI.connect((self.ip, self.port))
            return cfg.RETURN_CODE.SUCCESS
        except:
            print("Client (%s, %s) is offline")
            return cfg.RETURN_CODE.ERR_NOT_CONNECTED

    def sendMsg(self, msg):
        try:
            self.connexionRPI.send(msg.encode())
            return cfg.RETURN_CODE.SUCCESS
        except:
            print("Client (%s, %s) is offline")
            self.deconnexion()
            return cfg.RETURN_CODE.ERR_NOT_CONNECTED

    def deconnexion(self):
        print("Closing the connection")
        self.connexionRPI.close()
