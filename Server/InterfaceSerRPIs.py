import socket

class InterfaceSerRPIs:
    def __init__(self, ip):
        self.ip = ip
        self.port = 8888
        self.connexion_RPI = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connexion_RPI.connect((self.ip, self.port))
        print("Connexion établie avec le serveur sur le port {}".format(self.port))

    def launch_connexion(self, cmd):
        # ~ self.connect_to_RPI()
        self.envoi_msg(cmd)

    def presence(self):
        self.envoi_msg('Connected ?')
        self.deconnexion()

    def envoi_msg(self, msg):
        # ~ msg_a_envoyer = b""
        self.connexion_RPI.send(msg.encode())

    def deconnexion(self):
        print("Fermeture de la connexion")
        self.connexion_RPI.close()