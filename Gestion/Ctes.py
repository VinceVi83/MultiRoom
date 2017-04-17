__author__ = 'vinsento'


"""
TODO : acces via a database or a config file
"""
import subprocess
import netifaces as ni

local_ip = ni.ifaddresses('enp4s0f1')[2][0]['addr']

def getVarEnvironnement(var):
    return subprocess.check_output("echo $" + var, shell=True).decode().strip()

user_vlc = getVarEnvironnement("user_vlc")
pwd_vlc = getVarEnvironnement("pwd_vlc")

# TODO : Create a user or change right of some files
user_linux = getVarEnvironnement("user_linux")
pwd_linux = getVarEnvironnement("pwd_linux")

# Path
path_home = '/home/' + user_linux + '/'
path_cron = '/var/spool/cron/crontabs/'
path_playlist = getVarEnvironnement("path_playlist")

'''
Constants by default
'''
vlc = {}
vlc['pause'] = ['pl_pause']
vlc['stop'] = ['pl_stop']
vlc['play'] = ['pl_play']
vlc['next'] = ['pl_next']
vlc['prev'] = ['pl_previous']
vlc['dir'] = ['in_play&input=']

'''
If id=0 then items will be sorted in normal order, if id=1 they will be sorted in reverse order
A non exhaustive list of sort modes:
0 Id
1 Name
3 Author
5 Random
7 Track number
'''
vlc['order'] = ['pl_sort&id="0"&val=']
vlc['Rorder'] = ['pl_sort&id="1"&val=']
vlc['random'] = ['pl_random']
vlc['loop'] = ['pl_loop']
vlc['repeat'] = ['pl_repeat']
'''
Allowed values are of the form:
+<int>, -<int>, <int> or <int>%
'''
vlc['vol'] = ['volume&val=']
vlc['pwd'] = [pwd_vlc]
vlc['user'] = [user_vlc]

linux = {}
linux['pwd'] = [pwd_linux]
linux['user'] = [user_linux]
linux['home'] = [path_home]
linux['cron'] = [path_cron]
linux['playlist'] = [path_playlist]

'''
Mutagen argument to modify metadata
'''
mutagen_keys = {}
mutagen_keys['titre'] = ['TCOM']
mutagen_keys['artiste'] = ['TPE1']
mutagen_keys['album'] = ['TALB']
mutagen_keys['circle'] = ['TPE2']
mutagen_keys['genre'] = ['TCON']
mutagen_keys['commentaire'] = ['COMM']
mutagen_keys['copyright'] = ['TCOP']
mutagen_keys['langage'] = ['TLAN']
mutagen_keys['date'] = ['TDRC']
mutagen_keys['piste'] = ['TRCK']