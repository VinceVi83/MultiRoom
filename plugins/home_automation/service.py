from config_loader import cfg
from plugins.home_automation.ha_communication import CommunicationHA
from tools.llm_agent import llm


class HomeAutomationService:
    """Home Automation Service for daily operations.
    
    Methods:
        __init__(self) : Initialize the service with configuration and communication handlers.
        execute(self, context) : Execute home automation tasks using LLM agents to determine location and label.
        get_status(self) : Check if the service is online and return status information.
    """

    def __init__(self):
        self.plugin_name = "Daily" 
        self.config = cfg.home_automation
        self.ha_service = CommunicationHA()
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context):
        location_res = llm.execute(context.user_input, cfg.sys.Global.location_agent)
        context.label = llm.execute(context.user_input, cfg.home_automation.DOMOTIC_HA.DOMOTIC_AGENT)
        
        context.location = location_res.get('location', 'NONSENSE')
        print("VNG HomeAutomationService", context.label, context.location)
        return self.ha_service.handle_request(context)

    def get_status(self):
        """Utility function to check if the service responds."""
        print("OK")
        return {"status": "online", "plugin": self.plugin_name}
