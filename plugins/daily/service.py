from config_loader import cfg
from plugins.daily.shopping import ShoppingService
from tools.llm_agent import llm
from tools.utils import Utils

class DailyService:
    """Daily Service Plugin
    
    Role: Manages daily shopping list operations.
    
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
        try:
            is_fridge = any(w in context.user_input.lower() for w in ['frigo', 'fridge'])
            agent = cfg.daily.DAILY_USE.FRIDGE_AGENT if is_fridge else cfg.daily.DAILY_USE.DAILY_AGENT
            shopping = ShoppingService()

            res = llm.execute(context.user_input, agent)
            action = res.get('ACTION', 'NONE')
            context.sub_category = action
            context.add_step('sub_category', res)
            
            if "_ADD" in context.sub_category:
                new_items = llm.execute(context.user_input, cfg.daily.DAILY_USE.EXTRACT_FOOD_AGENT)
            elif action == 'NONE':
                return cfg.RETURN_CODE.ERR

            result = "NONSENSE"
            if context.sub_category == "SHOP_ADD":
                result = shopping.update_shopping_list(new_items)
            elif context.sub_category == "SHOP_DEL":
                result = shopping.delete_shopping_list()
            elif context.sub_category == "SHOP_INFO":
                result = shopping.report_shopping_list()
            elif context.sub_category == "SHOP_MAIL":
                result = shopping.mail_shopping_list()

            context.result = Utils.format_result(result)
            if result == "NONSENSE":
                return cfg.RETURN_CODE.ERR
            elif type(result) is type(cfg.RETURN_CODE.SUCCESS):
                return result
            return cfg.RETURN_CODE.SUCCESS
        
        except (ValueError, Exception) as e:
            print(f"[PLUGIN DailyService ERROR] {e}")
            return cfg.RETURN_CODE.ERR

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
