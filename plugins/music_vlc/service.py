from config_loader import cfg
from tools.llm_agent import llm
from plugins.music_vlc.vlc_user_manager import VLCUserManager
from tools.utils import Utils

class MusicVlcService:
    """MusicVlc Service
    
    Role: Manages music playback services using VLC with LLM integration for playlist and media control.
    
    Methods:
        __init__(self) : Initialize the MusicVLC service.
        execute(self, context) : Execute the main service logic with given context.
        execute_native(self, context) : Execute native service logic.
        _get_free_index(self) : Get a free instance index.
        check_user_use_service(self, context) : Check and create user service manager.
        get_status(self) : Check if the service responds and return status.
    """

    def __init__(self):
        self.plugin_name = "Music VLC" 
        self.cfg = cfg.music_vlc
        self.cfg.RETURN_CODE = cfg.RETURN_CODE
        self.active_instances = {}
        self.cfg.INTENT = ["UNKNOWN", "DISCOVERY", "PLAYLIST_AGENT", "VLC_AGENT", "DISCOVERY"]
        self.cfg.VLC_ACTIONS = ["UNKNOWN","TOGGLE", "PREVIOUS", "NEXT", "VOL_DOWN", "VOL_UP", "SHUFFLE", "INFO"]
        self.cfg.PLAYLIST_ACTION = ["UNKNOWN", "PLAY", "CREATE", "ADD_TO", "DELETE_TO", "INFO"]

        self.occupied_indexes = []
        if not self.cfg:
            return

    def execute(self, context):
        try:
            location = llm.execute(context.user_input, cfg.sys.Global.location_agent, timeout=10)
            result = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.MUSIC_AGENT, timeout=10)

            intent_id = Utils.to_int(result, "ID")
            context.label = self.cfg.INTENT.get(intent_id)
            context.location = Utils.to_str(location, "location")

            if context.label == "PLAYLIST_AGENT":
                res_pl = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.PLAYLIST_AGENT, timeout=10)
                context.result = Utils.format_result(res_pl)
                
            elif context.label == "VLC_AGENT":
                res_vlc = llm.execute(context.user_input, cfg.music_vlc.MUSIC_VLC.VLC_AGENT, timeout=10)
                vlc_id = Utils.to_int(res_vlc, "ID")
                context.result = self.cfg.VLC_ACTIONS.get(vlc_id)

            return self.execute_native(context)

        except Exception:
            return self.cfg.RETURN_CODE.ERR
    
    def execute_native(self, context):
        vlc_manager = self.check_user_use_service(context)
        if isinstance(vlc_manager, VLCUserManager):
            result = vlc_manager.interpret_vlc_command(context)
            if result != "NONSENSE":
                return self.cfg.RETURN_CODE.SUCCESS
        return self.cfg.RETURN_CODE.ERR

    def _get_free_index(self):
        for index, instance in self.active_instances.items():
            if not instance.is_alive():
                self.active_instances.pop(index)
            return index

        new_idx = max(self.active_instances.keys(), default=-1) + 1
        return new_idx

    def check_user_use_service(self, context):
        existing_mgr = context.session.services.get(self.plugin_name)
        if existing_mgr and isinstance(existing_mgr, VLCUserManager):
            if existing_mgr.is_alive():
                return existing_mgr
            else:
                del context.session.services[self.plugin_name]
        
        idx = self._get_free_index()
        if idx is None:
            return self.cfg.RETURN_CODE.ERR
        
        user_mgr = VLCUserManager(self.cfg, context.session.services, idx)
        res = context.session.add_new_service(self.plugin_name, user_mgr)
        
        if res == self.cfg.RETURN_CODE.SUCCESS:
            return user_mgr
        return self.cfg.RETURN_CODE.ERR

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
