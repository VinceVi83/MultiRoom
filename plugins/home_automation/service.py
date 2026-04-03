from plugins.home_automation.ha_communication import CommunicationHA
from plugins.home_automation.ha_listener import HAListener
from plugins.home_automation.ha_registry import HomeAutomationRegistry
from plugins.home_automation.ha_weather import WeatherHaApi, WeatherStatus
from tools.llm_agent import llm
from tools.utils import Utils

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
        self.ha_register = HomeAutomationRegistry(cfg)
        self.ha_register.update_device()
        self.ha_service = CommunicationHA(cfg)
        self.ha_listener = HAListener(cfg)
        self.ha_listener.run_ha_listener()
        self.ha_weather = WeatherHaApi(cfg)

        if not self.cfg:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute_native(self, context):
        try:
            params = {}
            if context.sub_category and (',' in context.sub_category or ':' in context.sub_category):
                params = dict(item.split(":") for item in context.sub_category.split(",") if ":" in item)
                context.params = params 
                return self.ha_service.handle_request(context)
            
        except Exception as e:
            print(f"Error parsing params in service: {e}")
            return self.cfg.RETURN_CODE.ERR

    def execute(self, context, callback_internal_request_api):
        try:
            result = llm.execute(context.user_input, self.cfg.DOMOTIC_AGENT)
            action, dtype = result.get('ACTION', 'NONE'), result.get('TYPE', 'NONE')
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
                context.result = "Failed"
            return result
        except Exception as e:
            print(f"[PLUGIN HomeAutomationService ERROR] {e}")
            return self.cfg.RETURN_CODE.ERR
    
    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
