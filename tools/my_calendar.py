import os
import sys
import requests
import vobject
import json
from datetime import datetime
from pathlib import Path
from datetime import timedelta
from config_loader import cfg
from tools.mailer_proton import send_mail

class CalendarService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CalendarService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.index_path = Path(cfg.DIR_DOCS) / "concert_tickets/concerts.json"
        self.status = self._run_health_check()
        self._initialized = True

    def _run_health_check(self):
        checks = {"json_file": False, "ical_url": False}

        if self.index_path.exists():
            checks["json_file"] = True
        try:
            r = requests.head(cfg.LINK_CALENDAR, timeout=5)
            if r.status_code == 200:
                checks["ical_url"] = True
        except:
            pass
        return checks

    def is_healthy(self):
        """Returns True if everything is OK, otherwise lists the errors."""
        if all(self.status.values()):
            return True, "All systems GO"
        errors = [k for k, v in self.status.items() if not v]
        return False, f"Issues detected: {', '.join(errors)}"

    def _get_calendar_events(self):
        """Fetches and parses the remote iCal file."""
        response = requests.get(cfg.LINK_CALENDAR, timeout=10)
        response.raise_for_status()
        calendar = vobject.readOne(response.text)

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
        """Filters the iCal events."""
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
        """Analyzes the JSON dictionary of tickets."""
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
        """Send the next concert by email with its attached file."""
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

            attachment = Path(cfg.DIR_DOCS) / "concert_tickets" / pdf_file
            success = send_mail(
                subject=subject,
                body=body,
                to_email=f"concert@{cfg.DOMAIN}",
                attachment_path=str(attachment) if attachment.exists() else None
            )
            return f"Success ({summary})" if success else "Failed to send email"

        except Exception as e:
            return f"Critical Error in Mail Service: {e}"

    def get_week_events(self, offset=0):
        """
        offset=0 : Current week
        offset=1 : Next week
        """
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
    cal = CalendarService()
    events = cal.fetch_calendar_events(limit=1)
    for e in events:
        print(f"Next: {e['summary']} on {e['dt']}")
