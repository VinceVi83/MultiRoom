#!/usr/bin/env python
# coding: utf-8

import socket

hote = "127.0.0.1"
port = 8888

socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
socket.connect((hote, port))
print("Connection on {}".format(8888))
keep = True
socket.send("toto.toto".encode())
while(keep):
    msg = "toto." + input()
    socket.send(msg.encode())
    if msg == "Fin":
        keep = False

socket.close()