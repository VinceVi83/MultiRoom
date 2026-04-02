from tools.llm_agent import llm
from plugins.music_vlc.vlc_user_manager import VLCUserManager
from tools.utils import Utils

class MusicVlcService:
    """Music VLC Service Plugin
    
    Role: Manages VLC music playback, playlist operations, and user session management.
    
    Methods:
        __init__(self): Initialize the service with configuration and active instances.
        execute(self, context): Process user input and execute music commands via LLM.
        execute_native(self, context): Execute native VLC commands through user manager.
        _get_free_index(self): Get or create a free instance index for active instances.
        check_user_use_service(self, context): Check and create user service manager.
        get_status(self): Return service status information.
    """
    def __init__(self, cfg):
        self.plugin_name = "Music VLC" 
        self.cfg = cfg
        self.cfg.RETURN_CODE = cfg.RETURN_CODE
        self.active_instances = {}
        self.cfg.INTENT = ["UNKNOWN", "PLAYLIST_AGENT", "DISCOVERY", "VLC_AGENT", "DISCOVERY"]
        self.cfg.VLC_ACTIONS = ["UNKNOWN","TOGGLE", "PREVIOUS", "NEXT", "VOL_DOWN", "VOL_UP", "SHUFFLE", "INFO"]
        self.cfg.PLAYLIST_ACTION = ["UNKNOWN", "PLAY", "CREATE", "ADD_TO", "DELETE_TO", "INFO"]

        self.occupied_indexes = []
        if not self.cfg:
            return

    def bypass_router(self, context):
        user_input_lower = context.user_input.lower()
        
        for keyword in self.cfg.config.BYPASS_ROUTER.PLAYLIST:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return "PLAYLIST"

        for keyword in self.cfg.config.BYPASS_ROUTER.MUSIC:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return "MUSIC"
        return None

    def execute(self, context):
        category_res = self.bypass_router(context)
        try:
            if category_res:
                context.add_step('sub_category', {'label': category_res, 'bypass': 1})
                context.sub_category = category_res
            else:
                category_res = llm.execute(context.user_input, self.cfg.MUSIC_AGENT)
                context.sub_category = category_res.get('CATEGORY', 'NONE')
                context.add_step('sub_category', category_res)
 
            if context.sub_category == 'PLAYLIST':
                res = llm.execute(context.user_input, self.cfg.PLAYLIST_AGENT)
            elif context.sub_category == 'MUSIC':
                res = llm.execute(context.user_input, self.cfg.VLC_AGENT)
            elif context.sub_category == 'DISCOVER':
                context.result = 'Done'
                return self.cfg.RETURN_CODE.SUCCESS
            else:
                res = {'ACTION': 'ERR'}

        except Exception as e:
                print(f"[PLUGIN MusicVlcService MUSIC_AGENT ERROR] {e}")
                return self.cfg.RETURN_CODE.ERR

        action = res.get('ACTION', 'ERR')
        context.add_step('Result', res)
        context.result = action
        return self.execute_native(context)

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
