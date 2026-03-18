from config_loader import cfg
from tools.llm_agent import llm
from plugins.music_vlc.vlc_user_manager import VLCUserManager

def format_result(result):
    if isinstance(result, dict):
        return ",".join([f"{k}:{v}" for k, v in result.items()])
    return str(result)


class MusicVlcService:
    """
    MusicVLC Service Class, manages music playback services using VLC with LLM integration for playlist and media control.

    Methods:
        __init__(self) : Initialize the MusicVLC service.
        execute(self, context) : Execute the main service logic with given context.
        get_status(self) : Check if the service responds and return status.
    """

    def __init__(self):
        self.plugin_name = "Music VLC" 
        self.config = cfg.music_vlc
        self.active_instances = {}
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def _get_free_index(self):
        occupied_indexes = {inst.index for inst in self.active_instances.values()}
        for i in range(5):
            if i not in occupied_indexes:
                return i
        return None

    def check_user_use_service(self, context):
        if self.plugin_name in context.session.services:
            return context.session.services[self.plugin_name]
        
        idx = self._get_free_index()
        if idx is None:
            return cfg.RETURN_CODE.NOTHING_TO_DO
        
        self.cleanup_inactive_services()
        user_mgr = VLCUserManager(context.session.services, context.session.index)
        res = context.session.add_new_service(self.plugin_name, user_mgr)
        if res == cfg.RETURN_CODE.SUCCESS:
            self.active_instances[id(user_mgr)] = user_mgr
            return user_mgr
        
        return cfg.RETURN_CODE.ERR

    def cleanup_inactive_services(self):
        self.active_instances = {k: v for k, v in self.active_instances.items() 
                                if v.process and v.process.poll() is None}

    def execute(self, context):
        location = llm.execute(context.user_input, cfg.sys.Global.location_agent)
        result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.MUSIC_AGENT)
        
        res = int(result.get('ID', '0'))
        
        context.label = cfg.music_vlc.AGENT_FEATURES[res].upper()
        context.location = location.get('location')

        result = "NONSENSE"
        if context.label == "PLAYLIST_AGENT":
            result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.PLAYLIST_AGENT)
        elif context.label == "VLC_AGENT":
            result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.VLC_AGENT)
            res = int(result.get('ID', '0'))
            result = cfg.music_vlc.LIST_VLC_FEATURE[res].upper()

        context.result = format_result(result)
        vlc_manager = self.check_user_use_service(context)
        if isinstance(vlc_manager, VLCUserManager):
            result = vlc_manager.interpret_vlc_command(context)

        if result != "NONSENSE":
            return cfg.RETURN_CODE.SUCCESS
        return cfg.RETURN_CODE.ERR

    def get_status(self):
        print("OK")
        return {"status": "online", "plugin": self.plugin_name}
