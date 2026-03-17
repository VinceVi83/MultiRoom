from config_loader import cfg
from plugins.daily.shopping import ShoppingService
from tools.llm_agent import llm
from tools.utils import FileUtils

class DailyService:
    """
    Daily Service Plugin - Manages daily shopping list operations.
    
    Methods:
        __init__(self) : Initialize the Daily Service plugin.
        execute(self, context) : Execute daily service commands based on LLM response.
        get_status(self) : Check if the service is responding.
    """

    def __init__(self):
        self.plugin_name = "Daily" 
        self.config = cfg.daily
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context):
        shopping = ShoppingService()
        result = llm.execute(context.user_input, cfg.daily.DAILY_USE.DAILY_AGENT)
        print(f"DEBUG LLM Output: {result}") 

        raw_id = result.get('ID', 'ERROR')
        try:
            res = int(raw_id)
        except (ValueError, TypeError):
            res = 0
            
        print(f"DailyService Index: {res}")
        print("DailyService", cfg.daily.AGENT_FEATURES, res, result)
        context.label = cfg.daily.AGENT_FEATURES[res]

        print("DailyService", context.label)

        result = cfg.RETURN_CODE.ERR
        if context.label == "SHOP_ADD":
            new_items = llm.execute(context.user_input, cfg.daily.DAILY_USE.EXTRACT_FOOD)
            result = shopping.update_shopping_list(new_items)
        elif context.label == "SHOP_DEL":
            result = shopping.delete_shopping_list()

        elif context.label == "SHOP_INFO":
            result = shopping.report_shopping_list()

        elif context.label == "SHOP_MAIL":
            result = shopping.mail_shopping_list()
        else:
            result = "NONSENSE"

        context.result = FileUtils.format_result(new_items)
        return result

    def get_status(self):
        print("OK")
        return {"status": "online", "plugin": self.plugin_name}

