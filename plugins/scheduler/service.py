import json, os, shlex, calendar, sched
from pathlib import Path
from datetime import datetime, timedelta
from config_loader import cfg
from tools.llm_agent import llm

class SchedulerService:
    def __init__(self):
        self.plugin_name = "scheduler"
        self.config = getattr(cfg, self.plugin_name.lower(), None)
        self.base_dir = Path(cfg.scheduler.DATA_DIR)
        self.db_path = self.base_dir / "cron_tasks.json"
        self.handler_script = Path(cfg.root) / "tools" / "hub_messenger.py"
        self.python_bin = "python3"
        self._ensure_db()

    def execute(self, context):
        time_data = llm.execute(context.user_input, self.config.SCHEDULER.TIME_EXTRACTOR)
        action = llm.execute(context.user_input, self.config.SCHEDULER.INTENT_AGENT)
        raw_cmd = action.get("action", context.user_input)
        tid = f"task_{int(datetime.now().timestamp())}"
        sched, run_time = self._build_schedule(time_data)
        full_shell_cmd = self._prepare_command(tid, raw_cmd, time_data.get("mode", "FIX"))
        return self._register_task(tid, raw_cmd, sched, full_shell_cmd, time_data.get("mode", "FIX"), run_time)

    def _build_schedule(self, d):
        p_type = d.get("mode", "FIX").upper()
        
        if p_type == "RECURRING":
            return f"{d.get('minute')} {d.get('hour')} * * {d.get('days', '*')}", None
        
        now = datetime.now()
        if p_type == "DELAY":
            # Utiliser .get() avec 0 par défaut pour éviter les erreurs
            minutes = int(d.get("minutes") or d.get("minute") or 0)
            hours = int(d.get("hours") or d.get("hour") or 0)
            target = now + timedelta(hours=hours, minutes=minutes)
        else:
            target = now.replace(hour=int(d.get("hour")), minute=int(d.get("minute")), second=0, microsecond=0)
            jumped, day = False, d.get("target_day", "today")
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            if day in days:
                diff = days.index(day) - now.weekday()
                if diff < 0 or (diff == 0 and target <= now):
                    diff += 7
                    jumped = True
                target += timedelta(days=diff)
            elif day == "tomorrow" or target <= now:
                target += timedelta(days=1)

            tf = d.get("timeframe", "none")
            if "_" in tf:
                try:
                    val, unit = tf.split('_')
                    v = int(val) - (1 if jumped else 0)
                    if v > 0:
                        if "week" in unit: target += timedelta(weeks=v)
                        elif "day" in unit: target += timedelta(days=v)
                        elif "month" in unit:
                            for _ in range(v):
                                nxt = (target.replace(day=1) + timedelta(days=32)).replace(day=1)
                                target = nxt.replace(day=min(target.day, calendar.monthrange(nxt.year, nxt.month)[1]))
                except: pass
        
        return f"{target.minute} {target.hour} {target.day} {target.month} *", target

    def _prepare_command(self, tid, cmd, p_type):
        mode = llm.execute(cmd, self.config.SCHEDULER.SYSTEM_AGENT)
        clean = f" && crontab -l | grep -v '#ID:{tid}' | crontab -" if p_type != "RECURRING" else ""
        exe = self.handler_script if mode.get("type", "SYSTEM") == "SYSTEM" else Path(cfg.root) / cfg.sys.SCRIPT_TTS
        return f"{self.python_bin} {exe} {shlex.quote(cmd)}{clean}"

    def _register_task(self, tid, raw_cmd, sched, full_cmd, p_type, dt):
        cron_line = f"{sched} {full_cmd.replace('%', '\\%')} #ID:{tid}"
        os.system(f"(crontab -l 2>/dev/null | grep -v '#ID:{tid}'; echo {shlex.quote(cron_line)}) | crontab -")
        
        with open(self.db_path, 'r+') as f:
            data = json.load(f)
            data["tasks"] = [t for t in data["tasks"] if t["id"] != tid]
            data["tasks"].append({"id": tid, "type": p_type, "schedule": sched, "cmd": raw_cmd, "ts": str(datetime.now())})
            f.seek(0); json.dump(data, f, indent=4); f.truncate()
            
        return f"Scheduled: {dt.strftime('%Y-%m-%d %H:%M')}" if dt else f"Recurring task set: {sched}"

    def _ensure_db(self):
        if not self.db_path.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w') as f: json.dump({"tasks": []}, f)
