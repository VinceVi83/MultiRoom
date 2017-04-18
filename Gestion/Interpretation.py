__author__ = 'VinceVi83'


"""
Command
"""

def cmd(user_service, command):
    # Example application.commande
    if command[0] is "VLC":
        if user_service.init == False:
            user_service.init_vlc(command[1], command[2:])
            return

    if command[1] is "kill":
        user_service.VLC.kill_vlc()
        user_service.stop_stream()
        return

    user_service.VLC.interpretation_command_vlc(command[1:])
    return

def cmdRPI():
    print("Not implemented")
    return
