__author__ = 'VinceVi83'




import os
from config_loader import cfg

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
        os.system('echo ' + cfg.LINUX_PWD + ' | sudo -S cp /var/spool/cron/crontabs/' + cfg.LINUX_USER + ' /var/spool/cron/crontabs/' + cfg.LINUX_USER + '.BAK')

    @staticmethod
    def memoriseAlarmMusicClock():
        """
        Replace the current file in crontab with the original
        :return:
        """
        os.system('echo ' + cfg.LINUX_PWD + ' | sudo -S cp /var/spool/cron/crontabs/' + cfg.LINUX_USER + '.BAK /var/spool/cron/crontabs/' + cfg.LINUX_USER)

    @staticmethod
    def setAlarmCalendar(self, horaires):
        '''
        Model Day ['min','heure','*','*','day','cmd']
        It's possible to do more specific schedule but for name it will be a simple it's depend of management
        '''
        os.system('echo ' + cfg.LINUX_PWD + ' | sudo -S cp /var/spool/cron/crontabs/' + cfg.LINUX_USER + '.BAK /home' + cfg.LINUX_USER + '/' + cfg.LINUX_USER)
        os.system('echo ' + cfg.LINUX_PWD + ' | sudo -S chmod 777 /home/' + cfg.LINUX_USER)
        fic = open('/home/' + cfg.LINUX_USER + '/' + cfg.LINUX_USER, 'a')
        jours = horaires.split("\n")
        for jour in jours:
            fic.write('\n')
            for param in jour:
                fic.write(str(param) + ' ')

        self.remove_file()
        os.system('echo ' + cfg.LINUX_PWD + ' | sudo -S cp /home' + cfg.LINUX_USER + '/' + cfg.LINUX_USER + ' /var/spool/cron/crontabs/' + cfg.LINUX_USER)

    @staticmethod
    def removeUserAlarmMusicClock(self):
        """
        Remove the current file in crontab
        :return:
        """
        os.system('echo ' + cfg.LINUX_PWD + ' | sudo -S rm /var/spool/cron/crontabs/' + cfg.LINUX_USER)
