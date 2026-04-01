from plugins.daily.shopping import ShoppingService
from tools.llm_agent import llm
from tools.utils import Utils

class DailyService:
    """Daily Service Plugin
    
    Role: Manages daily tasks including fridge queries and shopping list operations.
    
    Methods:
        __init__(self) : Initialize the DailyService plugin with configuration.
        execute(self, context) : Process daily commands and execute shopping actions.
        get_status(self) : Return plugin status information.
    """
    def __init__(self, cfg):
        self.plugin_name = "Daily" 
        self.cfg = cfg
        
        if not self.cfg:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def switch_fridge(self, context):
        user_input_lower = context.user_input.lower()
        
        for keyword in self.cfg.config.BYPASS_ROUTER.FRIDGE:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return True
        return False

    def execute(self, context):
        try:
            if self.switch_fridge(context):
                category_res = llm.execute(context.user_input, self.cfg.FRIDGE_AGENT)
                context.add_step('sub_category', category_res)
                action = category_res.get('ACTION', 'ERR')
                context.sub_category = action
                return self.cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED
            else:
                category_res = llm.execute(context.user_input, self.cfg.DAILY_AGENT)
                action = category_res.get('ACTION', 'ERR')
                context.sub_category = action
                context.add_step('sub_category', category_res)
            
            if "_ADD" in action:
                new_items = llm.execute(context.user_input, cfg.EXTRACT_FOOD_AGENT)
                if action == "SHOP_ADD":
                    result = shopping.update_shopping_list(new_items)
                else:
                    self.cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED
            else:
                result = self.shopping_service()

            context.result = Utils.format_result(result)
            if result == "NONSENSE":
                return cfg.RETURN_CODE.ERR
            elif type(result) is type(cfg.RETURN_CODE.SUCCESS):
                return result
            return cfg.RETURN_CODE.SUCCESS
        
        except (ValueError, Exception) as e:
            print(f"[PLUGIN DailyService ERROR] {e}")
            return cfg.RETURN_CODE.ERR

    def shopping_service(self):
        shopping = ShoppingService(self.cfg)
        result = "NONSENSE"
        if action == "SHOP_DEL":
            result = shopping.delete_shopping_list()
        elif action == "SHOP_INFO":
            result = shopping.report_shopping_list()
        elif action == "SHOP_MAIL":
            result = shopping.mail_shopping_list()
        return result

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
