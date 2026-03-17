from config_loader import cfg
from tools.llm_agent import llm


def format_result(result):
    if isinstance(result, dict):
        return ",".join([f"{k}:{v}" for k, v in result.items()])
    return str(result)


class MusicVlcService:
    """
    MusicVLC Service Class
    
    Methods:
        __init__(self) : Initialize the MusicVLC service.
        execute(self, context) : Execute the main service logic with given context.
        get_status(self) : Check if the service responds and return status.
    """

    def __init__(self):
        self.plugin_name = "Daily" 
        self.config = cfg.music_vlc
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context):
        location = llm.execute(context.user_input, cfg.sys.Global.location_agent)
        result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.MUSIC_AGENT)
        
        res = int(result.get('ID', '0'))
        
        context.label = cfg.music_vlc.AGENT_FEATURES[res].upper()
        print(cfg.music_vlc.AGENT_FEATURES, result, res)
        context.location = location.get('location')
        print("VNG MusicVlcService", result, context.label, context.location)


        if context.label == "PLAYLIST_AGENT":
            result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.PLAYLIST_AGENT)
            print("VNG MusicVlcService", result)
            context.result = format_result(result)
            return context.result
        elif context.label == "VLC_AGENT":
            result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.VLC_AGENT)
            print("VNG MusicVlcService", result)
            res = int(result.get('ID', '0'))
            context.result = cfg.music_vlc.LIST_VLC_FEATURE[res].upper()
            return context.result
        else:
            return "NONSENSE"

    def get_status(self):
        print("OK")
        return {"status": "online", "plugin": self.plugin_name}
        
