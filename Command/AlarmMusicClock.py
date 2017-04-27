__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from Gestion import Ctes
from Gestion.Enum import *

class AlarmMusicClock:
    '''
    TODO : change right on cron file
    Launch crontab -e avant use this oart of the code
    Feature to rec 
    '''


    @staticmethod
    def backupOriginal():
        """
        Save the original file
        :return:
        """
        os.system('echo ' + Ctes.pwd_linux + ' | sudo -S cp /var/spool/cron/crontabs/' + Ctes.user_linux + ' /var/spool/cron/crontabs/' + Ctes.user_linux + '.BAK')

    @staticmethod
    def memoriseAlarmMusicClock():
        """
        Replace the current file in crontab with the original
        :return:
        """
        os.system('echo ' + Ctes.pwd_linux + ' | sudo -S cp /var/spool/cnoteron/crontabs/' + Ctes.user_linux + '.BAK /var/spool/cron/crontabs/' + Ctes.user_linux)

    @staticmethod
    def setAlarmCalendar(self, horaires):
        '''
        Model Day ['min','heure','*','*','day','cmd']
        It's possible to do more specific schedule but for name it will be a simple it's depend of management
        '''
        os.system('echo ' + Ctes.pwd_linux + ' | sudo -S cp /var/spool/cron/crontabs/' + Ctes.user_linux + '.BAK /home' + Ctes.user_linux + '/' + Ctes.user_linux)
        os.system('echo ' + Ctes.pwd_linux + ' | sudo -S chmod 777 /home/' + Ctes.user_linux)
        fic = open('/home/' + Ctes.user_linux + '/' + Ctes.user_linux, 'a')
        jours = horaires.split("\n")
        for jour in jours:
            fic.write('\n')
            for param in jour:
                fic.write(str(param) + ' ')
        # memoriser ??? a ajouter
        self.remove_file()
        os.system('echo ' + Ctes.pwd_linux + ' | sudo -S cp /home' + Ctes.user_linux + '/' + Ctes.user_linux + ' /var/spool/cron/crontabs/' + Ctes.user_linux)

    @staticmethod
    def removeUserAlarmMusicClock(self):
        """
        Remove the current file in crontab
        :return:
        """
        os.system('echo ' + Ctes.pwd_linux + ' | sudo -S rm /var/spool/cron/crontabs/' + Ctes.user_linux)

