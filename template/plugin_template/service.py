# service.py
from config_loader import cfg
from tools.llm_agent import llm
from tools.utils import Utils
from plugins.your_plugin.logic_module import PluginLogic

class YourPluginService:
    """YourPlugin Service
    
    Role: Executes plugin logic with intent detection and action handling.
    
    Methods:
        __init__(self) : Initialize plugin service with configuration.
        execute(self, context) : Execute plugin logic based on user input.
        get_status(self) : Return online status of the plugin.
    """

    def __init__(self):
        self.plugin_name = "YourPlugin"
        self.config = getattr(cfg, self.plugin_name.lower(), None)
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context):
        logic = PluginLogic()
        
        intent_result = llm.execute(context.user_input, self.config.PLUGIN_NAME.INTENT_AGENT)
        intent_id = int(intent_result.get('ID', '0'))
        
        context.label = self.config.AGENT_FEATURES[intent_id]
        
        result = "NONSENSE"
        
        if context.label == "ACTION_ONE":
            extracted = llm.execute(context.user_input, self.config.PLUGIN_NAME.EXTRACT_DATA)
            result = logic.perform_action(extracted)
        elif context.label == "ACTION_TWO":
            result = logic.perform_action()

        context.result = Utils.format_result(result)
        if result == "NONSENSE":
            return cfg.RETURN_CODE.ERR
        return cfg.RETURN_CODE.SUCCESS

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
