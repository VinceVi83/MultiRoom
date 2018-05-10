__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket, select
from Server import Service
from Gestion import Ctes
from Gestion import Interpretation
from Gestion.Enum import *

CONNECTION_LIST = []  # list of socket clients
RECV_BUFFER = 4096  # Advisable to keep it as an exponent of 2
PORT = 8888
port = 8000
port_stream = 19000
port_ctrl = 9000


# Need Class ManageUsers
activeUser = {}

def serveur_master():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # this has no effect, why ?
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", PORT))
    server_socket.listen(10)
    VLCActivated = 0
    # Add server socket to the list of readable connections
    CONNECTION_LIST.append(server_socket)
    print("Chat server started on port " + str(PORT))
    send = ''

    while 1:
        # Get the list sockets which are ready to be read through select
        read_sockets, write_sockets, error_sockets = select.select(CONNECTION_LIST, [], [])


        for sock in read_sockets:
            #New connection
            if sock == server_socket:
                # Handle the case in which there is a new connection recieved through server_socket
                sockfd, addr = server_socket.accept()
                CONNECTION_LIST.append(sockfd)
                ip_cli, port = addr

            #Some incoming message from a client
            else:
                ip_cli, port = addr
                # Data recieved from client, process it
                try:
                    data = sock.recv(RECV_BUFFER)
                except:
                    print("Client (%s, %s) is offline", addr)
                    sock.close()
                    CONNECTION_LIST.remove(sock)
                    continue
                msg = data.decode()
                print("Message non split : " + msg)
                msg = msg.split(".")
                print(msg)
                # example first connexion  user.password
                if msg[0] not in activeUser.keys():
                    if msg[0] not in Ctes.users.keys():
                        sock.send("Denied".encode())
                        print("User not in database, " + msg[0])
                        sock.close()
                        CONNECTION_LIST.remove(sock)
                        continue
                    # TODO user account --> data base

                    print(msg[1] != Ctes.users[msg[0]])
                    if msg[1] != Ctes.users[msg[0]]:
                        print("Password not valid for " + msg[0] + "/" + msg[1] + "/")
                        sock.send("Denied".encode())
                        sock.close()
                        CONNECTION_LIST.remove(sock)
                        continue

                    print("user connected : " + msg[0])
                    activeUser[msg[0]] = Service.Service(port_ctrl + VLCActivated, port_stream + VLCActivated)
                    VLCActivated = VLCActivated + 1
                    sock.send("Connected".encode())
                else:
                    if msg[1] == 'end':
                        sock.close()
                        CONNECTION_LIST.remove(sock)
                        activeUser.pop(msg[0])
                        print("Client (%s, %s) is offline", addr)
                        continue

                    returncode = activeUser[msg[0]].cmd(msg[1:])
                    print(returncode)
                    if returncode == ReturnCode.ErrNotImplemented:
                        sock.send("Not implemented".encode())
