from config_loader import cfg
from tools.llm_agent import llm
from tools.utils import Utils
from plugins.your_plugin.logic_module import PluginLogic
import logging
logger = logging.getLogger(__name__)

class YourPluginService:
    """YourPlugin Service Plugin
    
    Role: Executes plugin logic with LLM-based intent recognition and action handling.
    
    Methods:
        __init__(self) : Initialize plugin with configuration.
        check_config(self) : Validate required configuration keys and return status.
        get_status(self) : Return plugin status information.
        execute(self, context, callback_internal_request_api) : Process user input and execute plugin actions.
    """
    def __init__(self):
        self.plugin_name = "YourPlugin"
        self.config = getattr(cfg, self.plugin_name.lower(), None)
        self.status = self.check_config()
        if self.status != self.cfg.RETURN_CODE.SUCCESS:
            return

    def check_config(self):
        required_keys = [
            # grep -r "self\.cfg\." plugins/music_vlc/ | grep -v "RETURN" | sed -n 's/.*self\.cfg\.\([a-zA-Z0-9._]*\).*/"\1",/p' | sort -u
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

    def execute(self, context, callback_internal_request_api):
        if not self.get_status():
            return self.cfg.RETURN_CODE.ERR
        logic = PluginLogic()
        
        intent_result = llm.execute(context.user_input, self.config.INTENT_AGENT)
        intent_id = int(intent_result.get('ID', '0'))
        
        context.sub_category = self.config.AGENT_FEATURES[intent_id]
        result = "NONSENSE"
        
        if context.sub_category == "ACTION_ONE":
            extracted = llm.execute(context.user_input, self.config.PLUGIN_NAME.EXTRACT_DATA)
            result = logic.perform_action(extracted)
        elif context.sub_category == "ACTION_TWO":
            result = logic.perform_action()

        context.result = Utils.format_result(result)
        if result == "NONSENSE":
            return cfg.RETURN_CODE.ERR
        return cfg.RETURN_CODE.SUCCESS
