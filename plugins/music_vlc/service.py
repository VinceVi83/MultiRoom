from tools.llm_agent import llm
from plugins.music_vlc.vlc_user_manager import VLCUserManager
from tools.utils import Utils
import logging
logger = logging.getLogger(__name__)

class MusicVlcService:
    """Music VLC Service Plugin
    
    Role: Manages VLC music playback, playlist operations, and user session management.
    
    Methods:
        __init__(self, cfg): Initialize the service with configuration and active instances.
        bypass_router(self, context): Route user input to playlist or music category.
        execute(self, context, callback_internal_request_api): Process user input and execute music commands via LLM.
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
        self.status = self.check_config()

        self.occupied_indexes = []
        if not self.cfg:
            return
        
    def check_config(self):
        required_keys = [
            "DATA_DIR",
            "INTENT",
            "MUSIC_AGENT",
            "PLAYLIST_ACTION",
            "PLAYLIST_AGENT",
            "VLC_ACTIONS",
            "VLC_AGENT",
            "config.BYPASS_ROUTER.MUSIC",
            "config.BYPASS_ROUTER.PLAYLIST",
            "config.LEN_ALBUMS_CACHE",
            "config.SMB_MOUNT_POINT",
            "config.VLC_PORT_START",
            "extra.BYPASS_MUSIC",
            "extra.BYPASS_PLAYLIST",
            "security.VLC_USERS"
        ]
        
        missing_keys = []

        for key_path in required_keys:
            keys = key_path.split('.')
            current_obj = self.cfg
            for key in keys:
                if not hasattr(current_obj, key):
                    missing_keys.append(key_path)
                    break
                current_obj = getattr(current_obj, key)

        if missing_keys:
            logger.error(f"Configuration {self.plugin_name} Error: Missing parameters: {', '.join(missing_keys)}")
            return self.cfg.RETURN_CODE.ERR_NOT_CONFIGURED
        
        logger.info(f"Configuration {self.plugin_name} successfully loaded.")
        return self.cfg.RETURN_CODE.SUCCESS
    
    def get_status(self):
        if self.status != self.cfg.RETURN_CODE.SUCCESS:
            logger.warn(f"{self.plugin_name} not configured")
            return False
        return True

    def bypass_router(self, context):
        user_input_lower = context.user_input.lower()
        
        fusion_list = self.cfg.config.BYPASS_ROUTER.PLAYLIST
        fusion_list += self.cfg.extra.BYPASS_PLAYLIST
        for keyword in fusion_list:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return "PLAYLIST"

        fusion_list = self.cfg.config.BYPASS_ROUTER.MUSIC
        fusion_list += self.cfg.extra.BYPASS_MUSIC
        for keyword in fusion_list:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return "MUSIC"
        return None

    def execute(self, context, callback_internal_request_api):
        if not self.get_status():
            return self.cfg.RETURN_CODE.ERR
        category_res = None
        if Utils.enable_bypass():
            category_res = self.bypass_router(context)

        try:
            if category_res:
                context.add_step('sub_category', {'label': category_res, 'bypass': 1})
                context.sub_category = category_res
            else:
                category_res = llm.execute(context.user_input, self.cfg.MUSIC_AGENT)
                context.sub_category = category_res.get('category', 'NONE')
                context.add_step('sub_category', category_res)
 
            if context.sub_category == 'PLAYLIST':
                vlc_manager = self.check_user_use_service(context)
                res = llm.execute(context.user_input, vlc_manager.playlist_agent)
                res = {'action': f'{res.get('action', 'ERR')}:{res.get('name', 'ERR')}'}
            elif context.sub_category == 'MUSIC':
                res = llm.execute(context.user_input, self.cfg.VLC_AGENT)
            elif context.sub_category == 'DISCOVER':
                context.result = 'Done'
                res = {'action': 'DISCOVER'}
            else:
                res = {'action': 'ERR'}
                return self.cfg.RETURN_CODE.ERR

        except Exception as e:
                logger.error(f"[PLUGIN MusicVlcService MUSIC_AGENT ERROR] {e}")
                return self.cfg.RETURN_CODE.ERR

        action = res.get('action', 'ERR')
        context.add_step('Result', res)
        context.result = action
        return self.execute_native(context)

    def execute_native(self, context):
        if not self.get_status():
            return self.cfg.RETURN_CODE.ERR
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
        
        user_mgr = VLCUserManager(self.cfg, context.session, idx)
        res = context.session.add_new_service(self.plugin_name, user_mgr)
        
        if res == self.cfg.RETURN_CODE.SUCCESS:
            return user_mgr
        return self.cfg.RETURN_CODE.ERR
