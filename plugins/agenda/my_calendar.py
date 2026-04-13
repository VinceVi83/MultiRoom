import requests
import vobject
import json
from thefuzz import fuzz
from datetime import datetime
from pathlib import Path
from datetime import timedelta
from config_loader import cfg
import logging
logger = logging.getLogger(__name__)

class CalendarService:
    """Calendar Service Plugin
    
    Role: Manages calendar event retrieval, filtering, and concert ticket notifications.
    
    Methods:
        __new__(cls) : Singleton pattern implementation.
        __init__(self) : Initialize service instance.
        _extract_event_data(self, vevent) : Extract event data from vevent object.
        _parse_datetime(self, dt_start) : Parse datetime from event.
        _get_calendar_events(self, config) : Fetch raw calendar events from URL.
        _filter_events(self, events, keyword, month) : Filter events by keyword and month.
        fetch_calendar_events(self, config, keyword='', month='', limit=None) : Filter and return calendar events.
        _parse_concert_key(self, key) : Parse concert key from index.
        get_next_concert_data(self, config) : Get next concert data from index file.
        _format_email_content(self, summary, date_str, pdf_file) : Format email content.
        mail_me_next_concert(self, config) : Email next concert details.
        _get_week_boundaries(self, offset=0) : Get week boundaries.
        get_week_events(self, config, offset=0) : Get events for a specific week.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CalendarService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.index_path = Path(cfg.agenda.DATA_DIR) / "concert_tickets/concerts.json"
        self._initialized = True

    def _extract_event_data(self, vevent):
        summary = ""
        location = ""
        dt_start = None

        if hasattr(vevent, 'summary'):
            summary = str(vevent.summary.value)

        if hasattr(vevent, 'location'):
            location = str(vevent.location.value)

        if hasattr(vevent, 'dtstart'):
            dt_start = vevent.dtstart.value

        return {
            "summary": summary if summary else "No Title",
            "location": location if location else "Unspecified Location",
            "dt": dt_start
        }

    def _parse_datetime(self, dt_start):
        if not dt_start:
            return None

        if isinstance(dt_start, datetime):
            dt_obj = dt_start.replace(tzinfo=None)
        else:
            dt_obj = datetime.combine(dt_start, datetime.min.time())

        return dt_obj

    def _get_calendar_events(self, config):
        try:
            response = requests.get(config.LINK_CALENDAR, timeout=10)
            response.raise_for_status()
            calendar = vobject.readOne(response.text)
        except (requests.RequestException, Exception) as e:
             logger.error(f"[!] Network error: Unable to fetch calendar: {e}")
             return []

        events = []
        vevent_list = getattr(calendar, 'vevent_list', [])

        for vevent in vevent_list:
            event_data = self._extract_event_data(vevent)
            dt_start = event_data["dt"]
            if dt_start:
                dt_obj = self._parse_datetime(dt_start)
                event_data["dt"] = dt_obj
                events.append(event_data)

        return sorted(events, key=lambda x: x["dt"])

    def _filter_events(self, events, keyword, month):
        filtered = []
        now = datetime.now()
        for event in events:
            if event["dt"] < now:
                continue
            if keyword and keyword.lower() not in event["summary"].lower():
                continue
            if month and event["dt"].strftime("%m") != month.zfill(2):
                continue
            filtered.append(event)
        return filtered

    def fetch_calendar_events(self, config, keyword="", month="", limit=None):
        all_events = self._get_calendar_events(config)
        filtered = self._filter_events(all_events, keyword, month)
        return filtered[:limit] if limit else filtered

    def _parse_concert_key(self, key):
        try:
            date_part = key.split(']')[0].strip('[')
            concert_name = key.split(']')[1].strip()
            return {
                "summary": concert_name,
                "dt": date_part,
                "pdf": None,
                "raw_key": key
            }
        except Exception:
            return None

    def get_next_concert_data(self, config):
        if not self.index_path.exists():
            return None

        events = self.fetch_calendar_events(config, keyword="Concert")
        if not events:
            return None
        with open(self.index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

        for event in events:
            event_title = event["summary"]
            best_pdf = None
            highest_score = 0

            for pdf_name, info in index.items():
                artist_in_json = info.get("data", {}).get("artist", "")
                if not artist_in_json:
                    continue

                score = fuzz.token_set_ratio(artist_in_json.upper(), event_title.upper())
                if score > highest_score:
                    highest_score = score
                    best_pdf = pdf_name

            if highest_score >= 80:
                event_key = f"[{event['dt'].strftime('%Y/%m/%d')}] {event_title}"
                
                return {
                    "summary": event_title,
                    "dt": event["dt"].strftime('%Y/%m/%d'),
                    "pdf": best_pdf,
                    "raw_key": event_key
                }
        return None

    def _format_email_content(self, summary, date_str, pdf_file):
        subject = f"🎵 Ticket & Info : {summary}"
        body = (
            f"Here are the details for your next concert:\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 EVENT : {summary}\n"
            f"📅 DATE      : {date_str}\n"
            f"📄 TICKET    : {pdf_file}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Enjoy the show!"
        )
        return subject, body

    def mail_me_next_concert(self, config):
        try:
            next_event = self.get_next_concert_data(config)
            if not next_event:
                return "Error: No concert found in index."

            summary = next_event["summary"]
            date_str = next_event["dt"]
            pdf_file = next_event["pdf"]

            subject, body = self._format_email_content(summary, date_str, pdf_file)
            attachment = Path(cfg.agenda.DATA_DIR) / "concert_tickets" / pdf_file
            attachment_path = str(attachment) if attachment.exists() else None

            data = {
                "api_name": "send_mail",
                "subject": subject,
                "body": body,
                "attachment": attachment_path
            }
            return data

        except Exception as e:
            logger.error(f"Critical Error in Mail Service: {e}")
            return {}

    def _get_week_boundaries(self, offset=0):
        now = datetime.now()
        start_of_current_week = now - timedelta(days=now.weekday())
        start_of_target_week = start_of_current_week + timedelta(weeks=offset)
        start_of_target_week = start_of_target_week.replace(hour=0, minute=0, second=0)
        end_of_target_week = start_of_target_week + timedelta(days=6, hours=23, minutes=59)
        return start_of_target_week, end_of_target_week

    def get_week_events(self, config, offset=0):
        all_events = self._get_calendar_events(config)
        start_of_target_week, end_of_target_week = self._get_week_boundaries(offset)

        filtered = [
            e for e in all_events
            if start_of_target_week <= e["dt"] <= end_of_target_week
        ]
        return filtered

if __name__ == "__main__":
    calendar = CalendarService()
    result = calendar.fetch_calendar_events(cfg.system.calendar, limit=1)
    print(result)
    result = calendar.fetch_calendar_events(cfg.system.calendar, limit=2)
    print(result)
    result = calendar.get_next_concert_data(cfg.system.calendar)
    print(result)
    result = calendar.mail_me_next_concert(cfg.system.calendar)
    print(result)
    result = calendar.get_week_events(cfg.system.calendar, 1)
    print(result)