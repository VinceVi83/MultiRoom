from plugins.agenda.my_calendar import CalendarService
from tools.llm_agent import llm
from tools.utils import Utils

class AgendaService:
    """Agenda Service Plugin
    
    Role: Manages calendar events and concert scheduling through LLM agent.
    
    Methods:
        __init__(self) : Initialize plugin with configuration.
        execute(self, context) : Process user input and execute calendar actions.
        get_status(self) : Return plugin status information.
    """
    def __init__(self, cfg):
        self.plugin_name = "Agenda" 
        self.cfg = cfg
        
        if not self.cfg:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context):
        try:
            if context is None:
                return cfg.RETURN_CODE.ERR
            
            calendar = CalendarService()
            res = llm.execute(context.user_input, cfg.AGENDA.CALENDAR_AGENT, False, False)
            action = res.get('ACTION', 'NONE')
            context.sub_category = action
            context.add_step('sub_category', res)
            
            result = "NONSENSE"
            if action == "NEXT_RDV":
                result = calendar.fetch_calendar_events(limit=1)
            elif action == "MAIL_NEXT_CONCERT" or "mail" in context.user_input:
                result = calendar.mail_me_next_concert()
            elif action == "NEXT_CONCERT":
                result = calendar.get_next_concert_data()
            elif action == "CURRENT_WEEK":
                result = calendar.get_week_events(0)
            elif action == "NEXT_WEEK":
                result = calendar.get_week_events(1)

            context.result = Utils.format_result(result)
            if result in ["NONSENSE"]:
                return cfg.RETURN_CODE.ERR
            return cfg.RETURN_CODE.SUCCESS
        except Exception as e:
            print(f"[PLUGIN AGENDA ERROR] {e}")
            return cfg.RETURN_CODE.ERR

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
