import json
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, fields, asdict, field
from config_loader import cfg, ReturnCode
from tools.utils import Utils

@dataclass
class TaskContext:
    """Task Context Manager
    
    Role: Manages task execution context, session data, and result reporting.
    
    Methods:
        __init__(self, user_input, session=None, audio_path=None, category='NONSENSE', label='NONSENSE', result='NONSENSE', duration_load=0, duration=0, duration_inference=0, location='NONSENSE', start=None, data=None, return_code=None) : Initialize task context with input, session, and metadata.
        add_step(self, step_name, data) : Add a step with data to the context.
        clone_safe(self) : Create a safe clone of the context with formatted return code.
        from_json(self, json_str) : Create TaskContext instance from JSON string.
        to_dict(self) : Convert context to dictionary, excluding session.
        display_report(self, new_audio_name='None') : Display formatted dispatch report.
        update_record(self, name) : Update archive record with current task data.
        _archive_and_rename(self) : Archive task files and rename with timestamp.
    """
    user_input: str
    session: any = None
    audio_path: str = None
    category: str = "NONSENSE"
    sub_category: str = "NONSENSE"
    result: str = "NONSENSE"
    duration_load: float = 0
    duration_inference: float = 0
    duration: int = 0
    location: str = "NONSENSE"
    start: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    data_request: dict = field(default_factory=dict)
    return_code: ReturnCode = cfg.RETURN_CODE.ERR
    call_counter: int = 0

    def add_step(self, step_name, data):
        self.data[step_name] = data

    def clone_safe(self):
        self.return_code = Utils.format_result(self.return_code)
        if isinstance(self.result, ReturnCode):
            self.result = self.result.name
        data = {f.name: getattr(self, f.name) for f in fields(self) if f.name != 'session'}
        return TaskContext(**data, session=None)

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return TaskContext(**data)

    def to_dict(self):
        data = asdict(self)
        data.pop('session', None)
        return data

    def display_report(self, new_audio_name="None"):
        print("\n" + "="*50)
        print(f"{'DISPATCH REPORT':^50}")
        print("="*50)
        print(f"{'Input:':<15} {self.user_input}")
        print(f"{'File:':<15} {new_audio_name}")
        print("-" * 50)
        print(f"{'Location:':<15} {self.location}")
        print(f"{'Category:':<15} {self.category}")
        print(f"{'Label:':<15} {self.sub_category}")
        print(f"{'Result:':<15} {Utils.format_result(self.result)}")
        print(f"{'ReturnCode:':<15} {Utils.format_result(self.return_code)}")
        print(f"{'Duration:':<15} {self.duration}s")
        print(f"{'LoadTimeLLM:':<15} {self.duration_load}s")
        print(f"{'InferenceTime:':<15} {self.duration_inference}s")
        print("="*50 + "\n")

    def add_durations(self, json_data: dict):
        try:
            self.duration_load += json_data.get('o_load', 0)
            self.duration_inference += json_data.get('inference_time', 0)
            self.call_counter += 1
        except Exception:
            pass

    def update_record(self, name):
        record_path = Path(cfg.DATA_DIR) / "Archive/record.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)

        records = []
        if record_path.exists():
            try:
                with open(record_path, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            except:
                records = []

        current_data = {
            "Success":     "True",
            "Command":     str(Utils.format_result(self.user_input)),
            "Category":    str(Utils.format_result(self.category)),
            "Subcategory": str(Utils.format_result(self.sub_category)),
            "Location":    str(Utils.format_result(self.location)),
            "Result":      str(Utils.format_result(self.result)),
            "ReturnCode":  str(Utils.format_result(self.return_code)),
            "audio_path":  str(Utils.format_result(name))
        }

        records.append(current_data)
        with open(record_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=4, ensure_ascii=False)

    def _archive_and_rename(self):
        try:
            if "NONSENSE" in [self.category, self.sub_category]:
                return self.clone_safe()

            timestamp = int(time.time())
            base = f"{timestamp}_{self.category}_{self.sub_category}"

            archive_dir = Path(cfg.DATA_DIR) / "Archive"
            dest_path, new_name = Utils.get_unique_path(archive_dir, base, ".wav")

            self.display_report(new_name)

            if self.audio_path and Path(self.audio_path).exists():
                shutil.move(self.audio_path, dest_path)
                self.audio_path = str(dest_path)
                self.update_record(new_name)

            return self.clone_safe()

        except Exception as e:
            print(f"[!] Error archiving in TaskContext : {e}")
            return self.clone_safe()
