import os
import sys
import shutil
import argparse
from pathlib import Path
from dotenv import dotenv_values

def get_env_vars(filepath):
    if not filepath or not os.path.exists(filepath):
        return {}
    return dotenv_values(filepath)

def append_missing_vars(target_file, missing_vars_dict, mode_label):
    if not missing_vars_dict:
        return

    with open(target_file, 'a', encoding='utf-8') as f:
        f.write(f"\n\n# MIGRATION: {mode_label} ---\n")
        for key, value in missing_vars_dict.items():
            val_str = value if value is not None else ""
            f.write(f"{key}={val_str}\n")

def migrate_pair(source_path, target_path, mode_label):
    if not source_path.exists():
        return

    if not target_path.exists():
        shutil.copy(source_path, target_path)
        return

    source_vars = get_env_vars(source_path)
    target_vars = get_env_vars(target_path)

    to_transfer = {k: v for k, v in source_vars.items() if k not in target_vars}

    if to_transfer:
        append_missing_vars(target_path, to_transfer, mode_label)
    else:
        pass

def run_migration(reverse=False):
    ROOT = Path(__file__).resolve().parent.parent 
    DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
    
    mode_label = "REVERSE (Data -> Template)" if reverse else "NORMAL (Template -> Data)"

    if reverse:
        migrate_pair(DATA_DIR / ".env", ROOT / ".env_template", mode_label)
    else:
        src = ROOT / ".env_template" if (ROOT / ".env_template").exists() else ROOT / ".env"
        migrate_pair(src, DATA_DIR / ".env", mode_label)

    src_plugins_dir = (DATA_DIR / "plugins") if reverse else (ROOT / "plugins")
    
    if src_plugins_dir.exists():
        for folder in src_plugins_dir.iterdir():
            if not folder.is_dir() or folder.name.startswith("__"):
                continue
            
            plugin_name = folder.name
            
            if reverse:
                src_env = folder / ".env"
                dst_env = ROOT / "plugins" / plugin_name / ".env_template"
            else:
                src_env = folder / ".env_template" if (folder / ".env_template").exists() else folder / ".env"
                dst_dir = DATA_DIR / "plugins" / plugin_name
                dst_dir.mkdir(parents=True, exist_ok=True)
                dst_env = dst_dir / ".env"

            migrate_pair(src_env, dst_env, mode_label)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reverse", action="store_true")
    args = parser.parse_args()
    run_migration(reverse=args.reverse)
