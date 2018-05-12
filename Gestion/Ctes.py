__author__ = 'VinceVi83'

# !/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
TODO : acces via a database or a config file
"""
import subprocess
import netifaces as ni



def getVarEnvironnement(var):
    return subprocess.check_output("echo $" + var, shell=True).decode().strip()

interface = getVarEnvironnement("interface")
local_ip = ni.ifaddresses(interface)[2][0]['addr']
user_vlc = getVarEnvironnement("user_vlc")
pwd_vlc = getVarEnvironnement("pwd_vlc")

# TODO : Create a user or change right of some files
user_linux = getVarEnvironnement("user_linux")
pwd_linux = getVarEnvironnement("pwd_linux")

# Path
path_home = '/home/' + user_linux + '/'
path_cron = '/var/spool/cron/crontabs/'
path_playlist = getVarEnvironnement("path_playlist")

# User tempory method
users = {}
users["toto"] = "toto"

'''
Constants by default
'''
vlc = {}
vlc['pause'] = 'pl_pause' # OK
vlc['stop'] = 'pl_stop' # OK
vlc['play'] = 'pl_play' # OK
vlc['next'] = 'pl_next' # OK
vlc['prev'] = 'pl_previous' # OK
vlc['dir'] = 'in_play&input=' # KO

'''
If id=0 then items will be sorted in normal order, if id=1 they will be sorted in reverse order
A non exhaustive list of sort modes:
0 Id
1 Name
3 Author
5 Random
7 Track number
'''
vlc['order'] = 'pl_sort&id="0"&val='
vlc['Rorder'] = 'pl_sort&id="1"&val='
vlc['random'] = 'pl_random' # OK
vlc['loop'] = 'pl_loop' # loop by default for dev
vlc['repeat'] = 'pl_repeat'
'''
Allowed values are of the form:
+<int>, -<int>, <int> or <int>%
'''
vlc['vol'] = 'volume&val=' # KO should be done on VLC client
vlc['pwd'] = pwd_vlc
vlc['user'] = user_vlc

linux = {}
linux['pwd'] = pwd_linux
linux['user'] = user_linux
linux['home'] = path_home
linux['cron'] = path_cron
linux['playlist'] = path_playlist

'''
Mutagen argument to modify metadata
It's so difficult remember tag...
'''
mutagen_keys = {}
mutagen_keys['TCOM'] = 'title'
mutagen_keys['TPE1'] = 'artist'
mutagen_keys['TALB'] = 'album'
mutagen_keys['TPE2'] = 'circle'
mutagen_keys['TCON'] = 'genre'
mutagen_keys['COMM::XXX'] = 'comment'
mutagen_keys['TLAN'] = 'langage'
"""
mutagen_keys['titre'] = 'TCOM'
mutagen_keys['artiste'] = 'TPE1'
mutagen_keys['album'] = 'TALB'
mutagen_keys['circle'] = 'TPE2'
mutagen_keys['genre'] = 'TCON'
mutagen_keys['commentaire'] = 'COMM::XXX'
mutagen_keys['copyright'] = 'TCOP'
mutagen_keys['langage'] = 'TLAN'
mutagen_keys['date'] = 'TDRC'
mutagen_keys['piste'] = 'TRCK'
"""
# Need to be fill by file or database by user
listRPIs = []
