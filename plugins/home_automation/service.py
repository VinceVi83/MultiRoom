from plugins.home_automation.ha_communication import CommunicationHA
from plugins.home_automation.ha_listener import HAListener
from plugins.home_automation.ha_registry import HomeAutomationRegistry
from plugins.home_automation.ha_weather import WeatherHaApi, WeatherStatus
from tools.llm_agent import llm
import logging
logger = logging.getLogger(__name__)

class HomeAutomationService:
    """Home Automation Service Plugin
    
    Role: Orchestrates Home Assistant interactions, weather status checks, and LLM-based command execution.
    
    Methods:
        __init__(self, cfg) : Initialize the service with configuration, HA communication, and weather API.
        execute_native(self, context) : Execute native requests with parameter parsing from sub_category.
        execute(self, context, callback_internal_request_api) : Main execution method that processes LLM commands and handles weather/HA requests.
        get_status(self) : Return the plugin status information.
    """
    def __init__(self, cfg):
        self.plugin_name = "Home Automation"
        self.cfg = cfg
        self.status = self.check_config()
        if self.status != self.cfg.RETURN_CODE.SUCCESS:
            return
        self.ha_register = HomeAutomationRegistry(cfg)
        self.ha_register.update_device()
        self.ha_service = CommunicationHA(cfg)
        self.ha_listener = HAListener(cfg)
        self.ha_listener.run_ha_listener()
        self.ha_weather = WeatherHaApi(cfg)

        if not self.cfg:
            logger.info(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def check_config(self):
        required_keys = [
            "DATA_DIR",
            "RETURN_CODE",
            "DOMOTIC_AGENT",
            "ha_config.HA_HOSTNAME",
            "ha_config.HA_TOKEN",
            "ha_config.HA_WEATHER_LOCATION"
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

    def execute_native(self, context):
        if not self.get_status():
            return self.cfg.RETURN_CODE.ERR
        try:
            params = {}
            if context.sub_category and (',' in context.sub_category or ':' in context.sub_category):
                params = dict(item.split(":") for item in context.sub_category.split(",") if ":" in item)
                context.params = params
                return self.ha_service.handle_request(context)
            
        except Exception as e:
            logger.error(f"parsing params in service: {e}")
            return self.cfg.RETURN_CODE.ERR

    def execute(self, context, callback_internal_request_api):
        if not self.get_status():
            return self.cfg.RETURN_CODE.ERR
        try:
            result = llm.execute(context.user_input, self.cfg.DOMOTIC_AGENT)
            action, dtype = result.get('action', 'NONE'), result.get('type', 'NONE')
            context.sub_category = f"{dtype}:{action}"
            context.add_step('sub_category', result)

            if "WEATHER" in context.sub_category:
                result = self.ha_weather.fetch_current_status()
                if isinstance(result, WeatherStatus):
                    context.result = result.display()
                    return self.cfg.RETURN_CODE.SUCCESS
            else:
                result = self.ha_service.handle_request(context)

            if result == self.cfg.RETURN_CODE.SUCCESS:
                context.result = "Executed"
            else:
                context.result = "Already Executed"
            return result
        except Exception as e:
            logger.error(f"[PLUGIN HomeAutomationService ERROR] {e}")
            return self.cfg.RETURN_CODE.ERR
    
    def get_status(self):
        if self.status != self.cfg.RETURN_CODE.SUCCESS:
            logger.warn(f"Home Automation not configured")
            return False
        return True
