__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

from Server.InterfaceSerRPIs import InterfaceSerRPIs
from Gestion.Enum import *
from Gestion import Ctes
import time

class ScannerRPI:
    def __init__(self):
        self.listRPIConnected = []
        self.listRPIDisconnected = Ctes.listRPIs.copy()
        # May have a multi-threading acces problem in near future
        self.hasBeenModified = False
        self.beingProcessed = False

    def addSlaveRPI(self, ip):
        if ip in self.listRPIDisconnected:
            return ReturnCode.ErrIllegalIP

        if ip not in self.listRPIConnected:
            self.listRPIConnected.append(ip)
            self.listRPIDisconnected.pop(ip)
            return ReturnCode.Succes
        else:
            return ReturnCode.ErrDuplicate

    def deleteSlaveRPI(self, ip):
        if ip in self.listRPIConnected:
            self.listRPIConnected.pop(ip)
        if ip not in self.listRPIDisconnected:
            self.listRPIDisconnected.append(ip)
        else:
            return ReturnCode.ErrDuplicate
        return ReturnCode.Succes

    def regularScan(self):
        '''
        Scan by les sockets to update RPIs dis/connected.
        Feature for later the degraded mode, one day ^^.
        :return:
        '''
        retryRPIDisconnected = 0
        while True:
            returncode = ReturnCode.Null

            if self.beingProcessed:
                time.sleep(60)
                continue

            if len(self.listRPIConnected) > 0:
                returncode = self.scanRPI()
                retryRPIDisconnected += 1

            if retryRPIDisconnected == 5 and len(self.listRPIDisconnected) > 0:
                    retryRPIDisconnected = 0
                    returncode = self.scanRPI(False)

            if not self.hasBeenModified and returncode == ReturnCode.SuccesModified:
                self.hasBeenModified = True

            time.sleep(60)

    def scanRPI(self, connected=True):
        '''
        
        :param connected: To try to scan connected or disconnected RPIs
        :return: 
        '''

        modified = False
        # TODO : Check if tmpmethod can del or add a RPI
        if connected:
            callMethod = self.deleteSlaveRPI
            currentlist = self.listRPIConnected
        else:
            callMethod = self.addSlaveRPI
            currentlist = self.listRPIDisconnected

        for ip in currentlist:
            print('Try : ' + ip)
            try:
                InterfaceSerRPIs(ip)
                print(ip + ' is available')
            except:
                print(ip + ' is not available')
                callMethod(ip)
                modified = True
        if modified:
            return ReturnCode.SuccesModified
        return ReturnCode.Succes


rpi = ScannerRPI()
rpi.addSlaveRPI("127.0.0.1")
rpi.regularScan()
