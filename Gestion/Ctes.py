__author__ = 'vinsento'


"""
TODO : acces via a database or a config file
"""
import subprocess

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
# TODO : Manage a remote playlist dir
path_playlist = getVarEnvironnement("path_playlist")


class Ctes():
    """
    Database contain the value of constant needed to use this program
    Maybe I will need to add a function memory to record new entry for evolution of this programme
    And a function add new Constants from file create by memorydddd
    """

    def __init__(self):
        self.dico = {}

    def get(self, key):
        """
        Retrieve value from a key
        :param key:
        :return:
        """
        return self.dico[key]

    def set(self, attr, value):
        """
        Add new attr with value if it's already exist you can't modify it
        and ask you if you want really change and identify yourself if you have the right to do that
        :param attr:
        :param value:
        :return:
        """
        if attr in self.dico:
            self.setMaster()

        else:
            self.dico[attr] = value

    def setMaster(self, attr, value):
        """
        
        :param attr: 
        :param value: 
        :return: 
        """
        print("Implement later")
        """ 
        if attr in self.dico and Interpretation.Interpretation.decision():
            self.dico[attr] = value
        """

        return


"""
Constants by default
"""
vlc = Ctes()
vlc.set('pause', 'pl_pause')
vlc.set('stop', 'pl_stop')
vlc.set('play', 'pl_play')
vlc.set('next', 'pl_next')
vlc.set('prev', 'pl_previous')
vlc.set('dir', 'in_play&input=')
'''
If id=0 then items will be sorted in normal order, if id=1 they will be sorted in reverse order
A non exhaustive list of sort modes:
0 Id
1 Name
3 Author
5 Random
7 Track number
'''
vlc.set('order', "pl_sort&id='0'&val=")
vlc.set('Rorder', "pl_sort&id='1'&val=")
vlc.set('random', 'pl_random')
vlc.set('loop', 'pl_loop')
vlc.set('repeat', 'pl_repeat')
'''
Allowed values are of the form:
+<int>, -<int>, <int> or <int>%
'''
vlc.set('vol', 'volume&val=')
vlc.set('pwd', pwd_vlc)
vlc.set('user', user_vlc)

linux = Ctes()
linux.set('pwd', pwd_linux)
linux.set('user', user_linux)
linux.set('home', path_home)
linux.set('cron', path_cron)
linux.set('playlist', path_playlist)

"""
Mutagen argument to modify metadata
"""
mutagen_keys = Ctes()
mutagen_keys.set("titre", "TCOM")
mutagen_keys.set("artiste", "TPE1")
mutagen_keys.set("album", "TALB")
mutagen_keys.set("circle", "TPE2")
mutagen_keys.set("genre", "TCON")
mutagen_keys.set("commentaire", "COMM")
mutagen_keys.set("copyright", "TCOP")
mutagen_keys.set("langage", "TLAN")
mutagen_keys.set("date", "TDRC")
mutagen_keys.set("piste", "TRCK")
