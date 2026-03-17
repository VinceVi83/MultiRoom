import json
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, fields, asdict, field
from config_loader import cfg, ReturnCode
from tools.utils import FileUtils


@dataclass
class TaskContext:
    """
    Represents the context of a task, including user input, session, audio path, category, label, result, duration, and location.

    Methods:
        clone_safe(user_input, session=None) : Creates a safe clone of the TaskContext without the session.
        from_json(json_str) : Creates a TaskContext instance from a JSON string.
        to_dict() : Transforms the object into a dictionary for JSON transmission.
        display_report(new_audio_name="None") : Displays a report of the task context.
        _archive_and_rename() : Archives the audio file and renames it.
    """

    user_input: str
    session: any = None
    audio_path: str = None
    category: str = "NONSENSE"
    label: str = "NONSENSE"
    result: str = "NONSENSE"
    duration_llm: int = 0
    duration: int = 0
    location: str = "NONSENSE"
    start: float = field(default_factory=time.time)

    def clone_safe(self):
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
        result = self.result
        if isinstance(self.result, ReturnCode):
            result = self.result.name
        print("\n" + "="*50)
        print(f"{'DISPATCH REPORT':^50}")
        print("="*50)
        print(f"{'Input:':<15} {self.user_input}")
        print(f"{'File:':<15} {new_audio_name}")
        print("-" * 50)
        print(f"{'Location:':<15} {self.location}")
        print(f"{'Category:':<15} {self.category}")
        print(f"{'Label:':<15} {self.label}")
        print(f"{'Result:':<15} {result}")
        print(f"{'Duration:':<15} {self.duration}s")
        print(f"{'DurationLLM:':<15} {self.duration_llm}s")
        print("="*50 + "\n")

    def _archive_and_rename(self):
        try:
            timestamp = int(time.time())
            base = f"{timestamp}_{self.category}_{self.label}"

            archive_dir = Path(cfg.sys.DIR_DOCS) / "Archive"
            dest_path, new_name = FileUtils.get_unique_path(archive_dir, base, ".wav")

            self.display_report(new_name)

            if self.audio_path and Path(self.audio_path).exists():
                shutil.move(self.audio_path, dest_path)
                self.audio_path = str(dest_path)

            return self.clone_safe()

        except Exception as e:
            print(f"[!] Error archiving in TaskContext : {e}")
            return self.clone_safe()
