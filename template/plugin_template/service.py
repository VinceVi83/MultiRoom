# service.py
from config_loader import cfg
from tools.llm_agent import llm
from tools.utils import Utils
from plugins.your_plugin.logic_module import PluginLogic

class YourPluginService:
    """YourPlugin Service Plugin
    
    Role: Executes plugin logic with LLM-based intent recognition and action handling.
    
    Methods:
        __init__(self) : Initialize plugin with configuration.
        execute(self, context, callback_internal_request_api) : Process user input and execute plugin actions.
        get_status(self) : Return plugin status information.
    """
    def __init__(self):
        self.plugin_name = "YourPlugin"
        self.config = getattr(cfg, self.plugin_name.lower(), None)
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context, callback_internal_request_api):
        logic = PluginLogic()
        
        intent_result = llm.execute(context.user_input, self.config.INTENT_AGENT)
        context.add_durations(intent_result)
        intent_id = int(intent_result.get('ID', '0'))
        
        context.sub_category = self.config.AGENT_FEATURES[intent_id]
        result = "NONSENSE"
        
        if context.sub_category == "ACTION_ONE":
            extracted = llm.execute(context.user_input, self.config.PLUGIN_NAME.EXTRACT_DATA)
            context.add_durations(extracted)
            result = logic.perform_action(extracted)
        elif context.sub_category == "ACTION_TWO":
            result = logic.perform_action()

        context.result = Utils.format_result(result)
        if result == "NONSENSE":
            return cfg.RETURN_CODE.ERR
        return cfg.RETURN_CODE.SUCCESS

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
