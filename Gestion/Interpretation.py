__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

from Gestion.Enum import *

"""
Command
"""

def cmd(user_service, command):
    # Example application.commande
    if command[0] is "VLC":
        if not user_service.init:
            user_service.init_vlc(command[1], command[2:])
            return ReturnCode.Succes

    if command[1] is "kill":
        user_service.VLC.kill_vlc()
        user_service.stop_stream()
        return ReturnCode.Succes

    user_service.VLC.interpretationCommandVLC(command[1:])
    return

def cmdRPI():
    print("Not implemented for process automation purpose")
    return ReturnCode.Succes

def permissionUser():
    return ReturnCode.ErrNotImplemented
