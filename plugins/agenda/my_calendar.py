import os
import sys
import requests
import vobject
import json
from datetime import datetime
from pathlib import Path
from datetime import timedelta
from config_loader import cfg
from plugins.agenda.mailer_proton import MailerProton

class CalendarService:
    """Calendar Service
    
    Role: Manages calendar event retrieval, filtering, and concert ticket notifications.
    
    Methods:
        __new__(cls) : Singleton pattern implementation.
        __init__(self) : Initialize the service with health checks.
        _run_health_check(self) : Check if JSON file and ICal URL are accessible.
        is_healthy(self) : Return health status of the service.
        _get_calendar_events(self) : Fetch all events from calendar source.
        fetch_calendar_events(self, keyword='', month='', limit=None) : Filter events by keyword, month, limit.
        get_next_concert_data(self) : Get next concert from index file.
        mail_me_next_concert(self) : Send email about next concert.
        get_week_events(self, offset=0) : Get events for a specific week.
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
        self.status = self._run_health_check()
        self._initialized = True
        self.mailer_proton = MailerProton()

    def _run_health_check(self):
        checks = {"json_file": False, "ical_url": False}

        if self.index_path.exists():
            checks["json_file"] = True
        else:
            print(f"[WARN] File not found: {self.index_path}")
        try:
            r = requests.head(cfg.agenda.calendar.LINK_CALENDAR, timeout=5)
            if r.status_code == 200:
                checks["ical_url"] = True
        except requests.RequestException as e:
            print(f"[!] Calendar check failed (Network): {e}")
        return checks

    def is_healthy(self):
        return all(self.status.values()), "All systems GO" if all(self.status.values()) else f"Issues detected: {', '.join([k for k, v in self.status.items() if not v])}"

    def _get_calendar_events(self):
        try:
            response = requests.get(cfg.agenda.calendar.LINK_CALENDAR, timeout=10)
            response.raise_for_status()
            calendar = vobject.readOne(response.text)
        except (requests.RequestException, Exception) as e:
             print(f"[!] Network error: Unable to fetch calendar: {e}")
             return []

        events = []
        vevent_list = getattr(calendar, 'vevent_list', [])
        for vevent in vevent_list:
            summary = str(vevent.summary.value) if hasattr(vevent, 'summary') else "No Title"
            location = str(vevent.location.value) if hasattr(vevent, 'location') else "Unspecified Location"
            dt_start = vevent.dtstart.value if hasattr(vevent, 'dtstart') else None

            if dt_start:
                if isinstance(dt_start, datetime):
                    dt_obj = dt_start.replace(tzinfo=None)
                else:
                    dt_obj = datetime.combine(dt_start, datetime.min.time())

                events.append({
                    "summary": summary,
                    "location": location,
                    "dt": dt_obj
                })
        return sorted(events, key=lambda x: x["dt"])

    def fetch_calendar_events(self, keyword="", month="", limit=None):
        all_events = self._get_calendar_events()
        filtered = []
        now = datetime.now()

        for event in all_events:
            if event["dt"] < now:
                continue
            if keyword and keyword.lower() not in event["summary"].lower():
                continue
            if month and event["dt"].strftime("%m") != month.zfill(2):
                continue
            filtered.append(event)
        return filtered[:limit] if limit else filtered

    def get_next_concert_data(self):
        if not self.index_path.exists():
            return None

        with open(self.index_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data or not isinstance(data, dict):
            return None

        concerts_list = []
        for key, pdf_name in data.items():
            try:
                date_part = key.split(']')[0].strip('[')
                concert_name = key.split(']')[1].strip()
                concerts_list.append({
                    "summary": concert_name,
                    "dt": date_part,
                    "pdf": pdf_name,
                    "raw_key": key
                })
            except Exception:
                continue

        if not concerts_list:
            return None

        concerts_list.sort(key=lambda x: x["dt"])
        return concerts_list[0]

    def mail_me_next_concert(self):
        try:
            next_event = self.get_next_concert_data()
            if not next_event:
                return "Error: No concert found in index."

            summary = next_event["summary"]
            date_str = next_event["dt"]
            pdf_file = next_event["pdf"]

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

            attachment = Path(cfg.agenda.DATA_DIR) / "concert_tickets" / pdf_file
            success = self.mailer_proton.send_mail(
                subject=subject,
                body=body,
                to_email=f"system@{cfg.agenda.mail_server.DOMAIN}",
                attachment_path=str(attachment) if attachment.exists() else None
            )
            return f"Success ({summary})" if success else "Failed to send email"

        except Exception as e:
            return f"Critical Error in Mail Service: {e}"

    def get_week_events(self, offset=0):
        all_events = self._get_calendar_events()
        now = datetime.now()

        start_of_current_week = now - timedelta(days=now.weekday())
        start_of_target_week = start_of_current_week + timedelta(weeks=offset)
        start_of_target_week = start_of_target_week.replace(hour=0, minute=0, second=0)

        end_of_target_week = start_of_target_week + timedelta(days=6, hours=23, minutes=59)

        filtered = [
            e for e in all_events
            if start_of_target_week <= e["dt"] <= end_of_target_week
        ]
        return filtered


if __name__ == "__main__":
    calendar = CalendarService()
    result = calendar.fetch_calendar_events(limit=1)
    print(result)
    result = calendar.fetch_calendar_events(limit=2)
    print(result)
    result = calendar.get_next_concert_data()
    print(result)
    result = calendar.mail_me_next_concert()
    print(result)
    result = calendar.get_week_events(1)
    print(result)
