import json
import time
import shutil
from pathlib import Path
from dataclasses import dataclass, fields, asdict
from config_loader import cfg
from tools.utils import FileUtils

@dataclass
class TaskContext:
    user_input: str
    session: any = None
    audio_path: str = None
    category: str = "NONSENSE"
    label: str = "NONSENSE"
    result: str = "NONSENSE"
    duration: int = 0
    location: str = "NONSENSE"

    def clone_safe(self):
        data = {f.name: getattr(self, f.name) for f in fields(self) if f.name != 'session'}
        return TaskContext(**data, session=None)

    @staticmethod
    def from_json(json_str):
        data = json.loads(json_str)
        return TaskContext(**data)

    def to_dict(self):
        """Transforms the object into a dictionary for JSON transmission"""
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
        print(f"{'Label:':<15} {self.label}")
        print(f"{'Result:':<15} {self.result}")
        print(f"{'Duration:':<15} {self.duration}s")
        print("="*50 + "\n")

    def _archive_and_rename(self):
        try:
            timestamp = int(time.time())
            base = f"{timestamp}_{self.category}_{self.label}"

            archive_dir = Path(cfg.DIR_DOCS) / "Archive"
            dest_path, new_name = FileUtils.get_unique_path(archive_dir, base, ".wav")

            self.display_report(new_name)

            if self.audio_path and Path(self.audio_path).exists():
                shutil.move(self.audio_path, dest_path)
                self.audio_path = str(dest_path)

            return self.clone_safe()

        except Exception as e:
            print(f"[!] Error archiving in TaskContext : {e}")
            return self.clone_safe()
