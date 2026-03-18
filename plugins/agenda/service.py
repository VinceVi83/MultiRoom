from config_loader import cfg
from plugins.agenda.my_calendar import CalendarService
from tools.llm_agent import llm
from tools.utils import Utils

class AgendaService:
    """Agenda Service Plugin
    
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
        calendar = CalendarService()
        result = llm.execute(context.user_input, cfg.agenda.AGENDA.CALENDAR_AGENT)
        res = int(result.get('ID', '0'))
        context.label = cfg.agenda.AGENT_FEATURES[res]

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

    def get_status(self):
        print("OK")
        return {"status": "online", "plugin": self.plugin_name}

