from plugins.daily.shopping import ShoppingService
from tools.llm_agent import llm
from tools.utils import Utils

class DailyService:
    """Daily Service Plugin
    
    Role: Manages daily tasks including fridge queries and shopping list operations.
    
    Methods:
        __init__(self, cfg) : Initialize the DailyService plugin with configuration.
        switch_fridge(self, context) : Check if user input matches fridge bypass keywords.
        execute(self, context, callback_internal_request_api) : Process daily commands and execute shopping actions.
        shopping_service(self, context, callback_internal_request_api) : Handle shopping list operations.
        get_status(self) : Return plugin status information.
    """
    def __init__(self, cfg):
        self.plugin_name = "Daily" 
        self.cfg = cfg
        self.shopping = ShoppingService(self.cfg)
        if not self.cfg:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def switch_fridge(self, context):
        user_input_lower = context.user_input.lower()
        
        for keyword in self.cfg.config.BYPASS_ROUTER.FRIDGE:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return True
        return False

    def execute(self, context, callback_internal_request_api):
        try:
            if self.switch_fridge(context):
                category_res = llm.execute(context.user_input, self.cfg.FRIDGE_AGENT)
                context.add_durations(category_res)
                context.add_step('sub_category', category_res)
                action = category_res.get('ACTION', 'ERR')
                context.sub_category = action
                return self.cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED
            else:
                category_res = llm.execute(context.user_input, self.cfg.DAILY_AGENT)
                context.add_durations(category_res)
                action = category_res.get('ACTION', 'ERR')
                context.sub_category = action
                context.add_step('sub_category', category_res)
            if "_ADD" in action:
                new_items = llm.execute(context.user_input, self.cfg.EXTRACT_FOOD_AGENT)
                context.add_durations(new_items)
                if action == "SHOP_ADD":
                    result = self.shopping.update_shopping_list(new_items)
                else:
                    return self.cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED
            else:
                result = self.shopping_service(context, callback_internal_request_api)

            context.result = Utils.format_result(result)
            if result == "NONSENSE":
                return self.cfg.RETURN_CODE.ERR
            elif type(result) is type(self.cfg.RETURN_CODE.SUCCESS):
                return result
            return self.cfg.RETURN_CODE.SUCCESS
        
        except (ValueError, Exception) as e:
            print(f"[PLUGIN DailyService ERROR] {e}")
            return self.cfg.RETURN_CODE.ERR

    def shopping_service(self, context, callback_internal_request_api):
        result = "Failed"
        if context.sub_category == "SHOP_DEL":
            result = self.shopping.delete_shopping_list()
        elif context.sub_category == "SHOP_INFO":
            result = self.shopping.report_shopping_list()
        elif context.sub_category == "SHOP_MAIL":
            context.data_request = self.shopping.mail_shopping_list()
            result = 'Failed or Shopping list is empty'
            if context.data_request:
                result = callback_internal_request_api(context) 
                if result == self.cfg.RETURN_CODE.SUCCESS:
                    result = "Mail sent"

        if result != self.cfg.RETURN_CODE.SUCCESS:
            context.return_code = self.cfg.RETURN_CODE.ERR
        else:
            context.result = result
            context.return_code = self.cfg.RETURN_CODE.SUCCESS
        return result

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
