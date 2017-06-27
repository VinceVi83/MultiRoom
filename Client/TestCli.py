#!/usr/bin/env python
# coding: utf-8

import socket
import time
hote = "127.0.0.1"
port = 8888

socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket.connect((hote, port))
print("Connection on {}".format(8888))
keep = True
# Authentification
socket.send("toto.toto".encode())
time.sleep(1)


# Manual use
while(keep):
    msg = "toto." + input()
    socket.send(msg.encode())
    if msg == "Fin":
        keep = False

""" Test Purpose
socket.send("toto.VLC.start./run/media/vinsento/455B532D7757A5FD/Project/Test/".encode())
time.sleep(1)
socket.send("toto.VLC.random".encode())
time.sleep(1)
socket.send("toto.VLC.next".encode())
time.sleep(1)
while(keep):
    socket.send("toto.Music.info".encode())
    input()
    socket.send("toto.VLC.next".encode())
    time.sleep(8)
"""

socket.close()