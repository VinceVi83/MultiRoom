from plugins.daily.shopping import ShoppingService
from tools.llm_agent import llm
from tools.utils import Utils
import logging
logger = logging.getLogger(__name__)

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
        self.status = self.check_config()
        if self.status != self.cfg.RETURN_CODE.SUCCESS:
            return
        self.shopping = ShoppingService(self.cfg)

    def check_config(self):
        required_keys = [
            "DAILY_AGENT",
            "DATA_DIR",
            "EXTRACT_FOOD_AGENT",
            "FRIDGE_AGENT",
            "config.BYPASS_ROUTER.FRIDGE"
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
            logger.warning(f"{self.plugin_name} not configured")
            return False
        return True

    def switch_fridge(self, context):
        user_input_lower = context.user_input.lower()
        
        for keyword in self.cfg.config.BYPASS_ROUTER.FRIDGE:
            keyword_lower = keyword.lower()
            if keyword_lower in user_input_lower:
                return True
        return False

    def execute(self, context, callback_internal_request_api):
        if not self.get_status():
            return self.cfg.RETURN_CODE.ERR
        try:
            if self.switch_fridge(context):
                category_res = llm.execute(context.user_input, self.cfg.FRIDGE_AGENT)
                context.add_step('sub_category', category_res)
                action = category_res.get('action', 'ERR')
                context.sub_category = action
                return self.cfg.RETURN_CODE.ERR_NOT_IMPLEMENTED
            else:
                category_res = llm.execute(context.user_input, self.cfg.DAILY_AGENT)
                action = category_res.get('action', 'ERR')
                context.sub_category = action
                context.add_step('sub_category', category_res)
            if "_ADD" in action:
                new_items = llm.execute(context.user_input, self.cfg.EXTRACT_FOOD_AGENT)
                context.add_step('result', new_items)
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
            logger.error(f"[PLUGIN DailyService ERROR] {e}")
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
