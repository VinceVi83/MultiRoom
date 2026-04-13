from plugins.agenda.my_calendar import CalendarService
from plugins.agenda.mailer_proton import MailerProton
from tools.llm_agent import llm
from tools.utils import Utils
import logging
logger = logging.getLogger(__name__)

class AgendaService:
    """Agenda Service Plugin
    
    Role: Manages calendar events and concert scheduling through LLM agent.
    
    Methods:
        __init__(self, cfg) : Initialize plugin with configuration.
        execute_api(self, context, data) : Process API requests for mail sending.
        execute(self, context, callback_internal_request_api) : Process user input and execute calendar actions.
        get_status(self) : Return plugin status information.
    """
    def __init__(self, cfg):
        self.plugin_name = "Agenda" 
        self.cfg = cfg
        self.calendar = CalendarService()
        self.mail = MailerProton()

    def check_for_defaults(self, cfg):
        default_values = {
            "calendar.LINK_CALENDAR": "https://calendar.service.com/api/v1/user/token/calendar.ics",
            "mail.DOMAIN": "yourdomain.com",
            "mail.PWD_MAIL": "your_app_password",
            "mail.USERNAME": "Your_Full_Name",
            "mail.USER_MAIL": "system@yourdomain.com"
        }
        unfinished_configs = []

        for path, default in default_values.items():
            keys = path.split('.')
            current = cfg
            
            try:
                for key in keys:
                    current = getattr(current, key)
                
                if current == default:
                    unfinished_configs.append(path)
            except AttributeError:
                continue

        if unfinished_configs:
            logger.warning(f"User '{cfg.name}' configuration, ACTION REQUIRED: The following keys are still using default values: {', '.join(unfinished_configs)}")
            return self.cfg.RETURN_CODE.ERR_NOT_CONFIGURED
        
        logger.info(f"User '{cfg.name}' configuration: Verified (No defaults detected).")
        return self.cfg.RETURN_CODE.SUCCESS

    def execute_api(self, context, data):
        if self.check_for_defaults(context.session.cfg) != self.cfg.RETURN_CODE.SUCCESS:
            return self.cfg.RETURN_CODE.ERR_NOT_CONFIGURED
        if data.get("api_name", None) == "send_mail":
            return self.mail.send_mail(context.session.cfg.mail, data["subject"], data["body"], attachment_path=data["attachment"], debug=False)

    def execute(self, context, callback_internal_request_api):
        if self.check_for_defaults(context.session.cfg) != self.cfg.RETURN_CODE.SUCCESS:
            return self.cfg.RETURN_CODE.ERR_NOT_CONFIGURED
        try:
            if context is None:
                return self.cfg.RETURN_CODE.ERR
            
            res = llm.execute(context.user_input, self.cfg.CALENDAR_AGENT)
            action = res.get('action', 'NONE')
            context.sub_category = action
            context.add_step('sub_category', res)
            
            result = "NONSENSE"
            if action == "NEXT_RDV":
                result = self.calendar.fetch_calendar_events(context.session.cfg.calendar, limit=1)
            elif action == "MAIL_NEXT_CONCERT" or "mail" in context.user_input:
                data = self.calendar.mail_me_next_concert(context.session.cfg.calendar)
                result = self.mail.send_mail(context.session.cfg.mail, data["subject"], data["body"], attachment_path=data["attachment"], debug=False)
                if self.cfg.RETURN_CODE.SUCCESS:
                    result = "Sent"
                else:
                    result = "Error not sent"
            elif action == "NEXT_CONCERT":
                result = self.calendar.get_next_concert_data(context.session.cfg.calendar)
            elif action == "CURRENT_WEEK":
                result = self.calendar.get_week_events(context.session.cfg.calendar, 0)
            elif action == "NEXT_WEEK":
                result = self.calendar.get_week_events(context.session.cfg.calendar, 1)

            context.result = Utils.format_result(result)
            if result in ["NONSENSE"]:
                return self.cfg.RETURN_CODE.ERR
            return self.cfg.RETURN_CODE.SUCCESS
        except Exception as e:
            logger.error(f"[PLUGIN AGENDA ERROR] {e}")
            return self.cfg.RETURN_CODE.ERR

    def get_status(self):
        return {"status": "online", "plugin": self.plugin_name}
