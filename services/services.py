import time
from config_loader import cfg
from tools.llm_agent import llm
from tools.my_calendar import CalendarService
from tools.scraper import ScraperService
from services.shopping import ShoppingService

agents_dict = {
    "PLAYLIST_AGENT": cfg.RouterLLM_SUB.PLAYLIST_AGENT,
    "VLC_AGENT": cfg.RouterLLM_SUB.VLC_AGENT,
    "SHOP_ADD": cfg.RouterLLM_SUB.SHOP_ADD
}

class ServiceDispatcher:
    """
    Dispatcher static for executing commands.
    Centralizes business logic without polluting the RouterLLM.
    """
    @staticmethod
    def execute(context):
        """Entry point for routing to the appropriate service."""
        handlers = {
            "DOMOTIC_AGENT": ServiceDispatcher._handle_domotic,
            "CALENDAR_AGENT": ServiceDispatcher._handle_calendar,
            "MUSIC_AGENT": ServiceDispatcher._handle_music,
            "DAILY_AGENT": ServiceDispatcher._handle_daily,
            "INFO_AGENT": ServiceDispatcher._handle_info
        }
        handler = handlers.get(context.category)
        if handler:
            try:
                return handler(context)
            except Exception as e:
                print(f"[!] Error executing service {context.category}: {e}")
                return f"ERROR_SERVICE_{context.category}"

        return "NONSENSE"

    @staticmethod
    def _handle_daily(context):
        shopping = ShoppingService()
        if context.label == "SHOP_ADD":
            new_items = llm.execute(context.user_input, agents_dict["SHOP_ADD"])
            result = shopping.update_shopping_list(new_items)
            return "Ok"

        elif context.label == "SHOP_DEL":
            result = shopping.delete_shopping_list()
            return "Ok"

        elif context.label == "SHOP_INFO":
            result = shopping.report_shopping_list()
            return "Ok"

        elif context.label == "SHOP_MAIL":
            result = shopping.mail_shopping_list()
            return "Ok"
        else:
            return "NONSENSE"

    @staticmethod
    def _handle_calendar(context):
        calendar = CalendarService()
        if context.label == "NEXT_RDV":
            calendar.fetch_calendar_events(limit=1)
        elif context.label == "NEXT_CONCERT":
            calendar.get_next_concert_data()
        elif context.label == "CURRENT_WEEK":
            calendar.get_week_events(0)
        elif context.label == "NEXT_WEEK":
            calendar.get_week_events(1)
        elif context.label == "MAIL_NEXT_CONCERT":
            calendar.mail_me_next_concert()
        return "OK"

    @staticmethod
    def _handle_music(context):
        location = llm.execute(context.user_input, cfg.GlobalLLM.location_agent)
        context.location = location.get('location')
        if context.label == "PLAYLIST_AGENT":
            result = llm.execute(context.user_input, agents_dict["PLAYLIST_AGENT"])
            return format_result(result)
        elif context.label == "VLC_AGENT":
            result = llm.execute(context.user_input, agents_dict["VLC_AGENT"])
            code_id = result.get('ID')
            code_name = cfg.SUB_MAPPINGS["VLC_AGENT"].get(code_id, "NONSENSE")
            return format_result(code_name)
        else:
            return "NONSENSE"

    @staticmethod
    def _handle_domotic(context):
        location_res = llm.execute(context.user_input, cfg.GlobalLLM.location_agent)
        context.location = location_res.get('location', 'Nonsense')

        if context.label in ["LIGHTS", "ACTION"]:

            return "Domotic service executed"
        return "NONSENSE"

    @staticmethod
    def _handle_info(context):
        scraper = ScraperService()
        if context.label == "WEATHER":
            scraper.get_web_summary(context.user_input, cfg.GlobalLLM.weather_forecast)
        elif context.label == "WEB_FAST":
            scraper.get_web_discovery(context.user_input, cfg.GlobalLLM.french_research_agent)
        elif context.label == "WEB_DEEP":
            candidate = scraper.get_search_candidates(context.user_input, count=1)
            scraper.get_web_extraction(context.user_input, candidate, cfg.GlobalLLM.french_research_agent_extreme)
        return "OK"


def format_result(result):
    """
    Transforms a dictionary {'K': 'V'} into string "K:V".
    If the input is not a dictionary, returns the input as is.
    """
    if isinstance(result, dict):

        return ",".join([f"{k}:{v}" for k, v in result.items()])
    return str(result)
