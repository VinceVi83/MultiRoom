from config_loader import cfg
from plugins.agenda.my_calendar import CalendarService
from tools.llm_agent import llm
from tools.utils import Utils

class AgendaService:
    """Agenda Service Plugin
    
    Role: Manages calendar agenda operations including fetching events, concerts, and mailing next concert notifications.
    
    Methods:
        __init__(self) : Initialize the service with configuration.
        execute(self, context) : Execute the agenda service logic and return status.
        get_status(self) : Check if the service is responding.
    """

    def __init__(self):
        self.plugin_name = "Agenda" 
        self.config = cfg.agenda
        
        if not self.config:
            print(f"[!] Error: Configuration for {self.plugin_name} not found.")

    def execute(self, context):
        try:
            if context is None:
                return cfg.RETURN_CODE.ERR
            
            calendar = CalendarService()
            res = llm.execute(context.user_input, cfg.agenda.AGENDA.CALENDAR_AGENT, False, False)
            action = res.get('ACTION', 'NONE')
            context.label = action
            context.add_step('sub_category', res)
            
            result = "NONSENSE"
            if context.label == "NEXT_RDV":
                result = calendar.fetch_calendar_events(limit=1)
            elif context.label == "NEXT_CONCERT":
                result = calendar.get_next_concert_data()
            elif context.label == "CURRENT_WEEK":
                result = calendar.get_week_events(0)
            elif context.label == "NEXT_WEEK":
                result = calendar.get_week_events(1)
            elif context.label == "MAIL_NEXT_CONCERT":
                result = calendar.mail_me_next_concert()

            context.result = Utils.format_result(result)
            if result in ["NONSENSE"]:
                return cfg.RETURN_CODE.ERR
            return cfg.RETURN_CODE.SUCCESS
        except Exception as e:
            print(f"[PLUGIN AGENDA ERROR] {e}")
            return cfg.RETURN_CODE.ERR

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
