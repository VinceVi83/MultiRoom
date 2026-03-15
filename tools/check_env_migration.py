import os
import re
from pathlib import Path

OLD_ENV = ".env"
NEW_ENV = ".env_example"
PROJECT_DIR = "."

def get_env_vars(filepath):
    """Parses an environment file into a dictionary of keys and values."""
    vars_dict = {}
    if not os.path.exists(filepath):
        return vars_dict
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, val = line.split("=", 1)
                    vars_dict[key.strip()] = val.strip()
    return vars_dict

def scan_code_for_cfg_calls(directory):
    """Scans Python files for references to cfg.VARIABLE."""
    found_calls = set()
    blacklist = {"S", "NAME", "VARIABLE_NAME", "YOUR_VARIABLE"}

    regex = r"cfg\.([A-Z0-9_]+)"

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                with open(os.path.join(root, file), 'r', errors='ignore') as f:
                    matches = re.findall(regex, f.read())
                    for m in matches:
                        if m not in blacklist and len(m) > 1:
                            found_calls.add(m)
    return found_calls

def run_migration_check():
    """Performs an audit to compare old/new env files against actual code usage."""
    print("=== CONFIGURATION MIGRATION AUDIT ===\n")

    old_vars = get_env_vars(OLD_ENV)
    new_vars = get_env_vars(NEW_ENV)
    code_needs = scan_code_for_cfg_calls(PROJECT_DIR)

    missing_in_new = [v for v in old_vars if v not in new_vars]
    if missing_in_new:
        print(f"DELETED/MISSING VARIABLES (absent from the new .env):")
        for v in missing_in_new:
            usage = " [!] STILL USED IN CODE" if v in code_needs else ""
            print(f"   - {v}{usage}")
    else:
        print("No variables were forgotten in the new file.")

    added_in_new = [v for v in new_vars if v not in old_vars]
    if added_in_new:
        print(f"\nNEWLY ADDED VARIABLES:")
        for v in added_in_new:
            print(f"   - {v}")

if __name__ == "__main__":
    run_migration_check()
