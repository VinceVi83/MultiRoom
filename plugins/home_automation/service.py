from config_loader import cfg
from plugins.home_automation.ha_communication import CommunicationHA
from plugins.home_automation.ha_weather import MeteoHaApi, WeatherStatus
from tools.llm_agent import llm
from tools.utils import Utils


class HomeAutomationService:
    """Home Automation Service
    
    Role: Manages home automation operations including weather checks and device control.
    
    Methods:
        __init__(self) : Initialize the service with configuration and communication handlers.
        execute(self, context) : Execute home automation tasks using LLM agents to determine location and label.
        get_status(self) : Check if the service is online and return status information.
        execute_native(self, context) : Handles complex native commands with dictionary parsing.
    """

    def __init__(self):
        self.plugin_name = "Home Automation"
        self.config = cfg.home_automation
        self.ha_service = CommunicationHA()
        self.meteo = MeteoHaApi()

        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute_native(self, context):
        try:
            params = {}
            if context.label and (',' in context.label or ':' in context.label):
                params = dict(item.split(":") for item in context.label.split(",") if ":" in item)
                context.params = params 
                return self.ha_service.handle_request(context)
            
        except Exception as e:
            print(f"Error parsing params in service: {e}")
            return cfg.RETURN_CODE.ERR

    def execute(self, context):
        try:
            location_res = llm.execute(context.user_input, cfg.sys.Global.location_agent)
            result = llm.execute(context.user_input, cfg.home_automation.DOMOTIC_HA.DOMOTIC_AGENT)
            
            context.label = Utils.format_result(result)
            context.location = location_res.get('location', 'NONSENSE') if location_res else 'NONSENSE'

            if "WEATHER" in context.label:
                result = self.meteo.fetch_current_status()
                if isinstance(result, WeatherStatus):
                    context.result = result.display()
                    return cfg.RETURN_CODE.SUCCESS
            else:
                result = self.ha_service.handle_request(context)

            if result == cfg.RETURN_CODE.SUCCESS:
                context.result = "Executed"
            else:
                context.result = "Failed"
            return result
        except Exception as e:
            print(f"[PLUGIN HomeAutomationService ERROR] {e}")
            return cfg.RETURN_CODE.ERR

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
