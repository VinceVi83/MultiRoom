import json
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, fields, asdict, field
from config_loader import cfg, ReturnCode
from tools.utils import Utils
from tools.llm_agent import llm
import random
import copy
import logging
logger = logging.getLogger(__name__)


@dataclass
class TaskContext:
    """Task Context Manager
    
    Role: Manages task execution context, session data, and result reporting.
    
    Methods:
        __init__(self, user_input, session=None, audio_path=None, category='NONSENSE', sub_category='NONSENSE', result='NONSENSE', duration_load=0, duration_inference=0, duration=0, location='NONSENSE', start=None, data=None, data_request=None, return_code=None, call_counter=0) : Initialize task context with input, session, and metadata.
        add_step(self, step_name, data, bypass=False) : Add a step with data to the context.
        clone_safe(self) : Create a safe clone of the context with formatted return code.
        from_json(self, json_str) : Create TaskContext instance from JSON string.
        to_dict(self) : Convert context to dictionary, excluding session.
        display_report(self, new_audio_name='None') : Display formatted dispatch report.
        add_durations(self, json_data) : Add duration metrics from JSON data.
        update_record(self, name) : Update archive record with current task data.
        _archive_and_rename(self) : Archive task files and rename with timestamp.
        report_action_status(self) : Generate and return action status report.
    """
    user_input: str
    session: any = None
    audio_path: str = None
    category: str = "NONSENSE"
    sub_category: str = "NONSENSE"
    result: str = "NONSENSE"
    duration_load: float = 0
    duration_inference: float = 0
    duration: float = 0
    location: str = "NONSENSE"
    start: float = time.time()
    data: dict = field(default_factory=dict)
    data_request: dict = field(default_factory=dict)
    return_code: ReturnCode = cfg.RETURN_CODE.ERR
    call_counter: int = 0

    def add_step(self, step_name, data, bypass=False):
        self.data[step_name] = data
        if bypass:
            return
        self.add_durations(data)

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

    def _build_report_header(self):
        header = f"{'='*50}\n"
        header += f"{'DISPATCH REPORT':^50}\n"
        header += f"{'='*50}\n"
        return header

    def _build_report_metadata(self):
        call_count = self.call_counter
        input_text = self.user_input
        file_name = self.audio_path if self.audio_path else "None"
        location = self.location
        category = self.category
        label = self.sub_category
        result = Utils.format_result(self.result)
        return_code = Utils.format_result(self.return_code)
        duration = self.duration
        load_time = self.duration_load
        inference_time = self.duration_inference
        metadata = (
            f"{'LLMCallCount:':<15} {call_count}\n"
            f"{'Input:':<15} {input_text}\n"
            f"{'File:':<15} {file_name}\n"
            f"{'-' * 50}\n"
            f"{'Location:':<15} {location}\n"
            f"{'Category:':<15} {category}\n"
            f"{'Label:':<15} {label}\n"
            f"{'Result:':<15} {result}\n"
            f"{'ReturnCode:':<15} {return_code}\n"
            f"{'Duration:':<15} {duration}s\n"
            f"{'LoadTimeLLM:':<15} {load_time}s\n"
            f"{'InferenceTime:':<15} {inference_time}s\n"
            f"{'='*50}"
        )
        return metadata

    def format_report(self, new_audio_name="None"):
        header = self._build_report_header()
        metadata = self._build_report_metadata()
        if new_audio_name != "None":
            metadata = metadata.replace("None", new_audio_name)
        return header + metadata

    def display_report(self, new_audio_name="None"):
        print(self.format_report(new_audio_name))

    def add_durations(self, json_data: dict):
        try:
            load_value = json_data.get('o_load', 0)
            inference_value = json_data.get('inference_time', 0)
            self.duration_load += load_value
            self.duration_inference += inference_value
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
            except Exception:
                records = []

        success_value = "True"
        command_value = str(Utils.format_result(self.user_input))
        category_value = str(Utils.format_result(self.category))
        subcategory_value = str(Utils.format_result(self.sub_category))
        location_value = str(Utils.format_result(self.location))
        result_value = str(Utils.format_result(self.result))
        return_code_value = str(Utils.format_result(self.return_code))
        audio_path_value = str(Utils.format_result(name))

        current_data = {
            "Success":     success_value,
            "Command":     command_value,
            "Category":    category_value,
            "Subcategory": subcategory_value,
            "Location":    location_value,
            "Result":      result_value,
            "ReturnCode":  return_code_value,
            "audio_path":  audio_path_value
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
            report = self.format_report(new_name)
            self.display_report(report)
            Utils.send_discord_notification(report)

            if self.audio_path and Path(self.audio_path).exists():
                shutil.move(self.audio_path, dest_path)
                self.audio_path = str(dest_path)
                self.update_record(new_name)

            return self.clone_safe()

        except Exception as e:
            logger.error(f"[!] Error archiving in TaskContext : {e}")
            return self.clone_safe()

    def report_action_status(self):
        report_input = (
            f"User Command: {self.user_input}\n"
            f"Status: {self.return_code}\n"
            f"Result: {self.result}"
        )
        try:
            selected_replica = random.choice(cfg.sys.personality.TSUNDERE)
            tmp_agent = copy.deepcopy(cfg.ALL_PURPOSE.TSUNDERE_V2_REPORT_AGENT)
            tmp_agent.prompt = tmp_agent.prompt.replace('RANDOM_REPLICA', selected_replica)
            report_text = llm.execute(report_input, tmp_agent)
            # self.add_step('report', report_text)
            report = report_text.get('content', 'FF')
            logger.info(f"\nALISU: {report}")
            Utils.send_discord_notification(f'A.L.I.S.U : {report}')
            return report

        except Exception as e:
            logger.error("Exception", e)
            if "success" in self.return_code:
                return f"Action completed: {self.user_input}."
            else:
                return "I'm sorry, I encountered an issue processing that request."
