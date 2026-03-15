import yaml
import os
from pathlib import Path

OLD_YAML = "agents_config.yaml"
NEW_YAML = "agents_config_new.yaml"

def get_yaml_structure(filepath):
    """Extract the Section -> Agent structure from the YAML file"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        structure = {}
        if isinstance(data, dict):
            for section, agents in data.items():
                if isinstance(agents, dict):
                    structure[section] = set(agents.keys())
        return structure
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return None

def run_audit():
    print("=== AUDIT OF YAML STRUCTURE ===\n")

    old_struct = get_yaml_structure(OLD_YAML)
    new_struct = get_yaml_structure(NEW_YAML)

    if old_struct is None or new_struct is None:
        print("Cannot compare: one of the files is missing or invalid.")
        return

    old_sections = set(old_struct.keys())
    new_sections = set(new_struct.keys())

    print("SECTION ANALYSIS:")
    missing_sections = old_sections - new_sections
    extra_sections = new_sections - old_sections

    if not missing_sections and not extra_sections:
        print("All sections match.")
    else:
        for s in missing_sections: print(f"Missing section: {s}")
        for s in extra_sections: print(f"New section: {s}")

    print("\nAGENT ANALYSIS:")
    has_error = False

    common_sections = old_sections & new_sections
    for section in common_sections:
        old_agents = old_struct[section]
        new_agents = new_struct[section]

        missing_agents = old_agents - new_agents
        extra_agents = new_agents - old_agents

        if missing_agents or extra_agents:
            print(f"--- Section: {section} ---")
            for a in missing_agents:
                print(f"Missing agent: {a}")
                has_error = True
            for a in extra_agents:
                print(f"New agent: {a}")

    if not has_error and not missing_sections:
        print("Structure is identical (or increased)! Migration is safe.")
    else:
        print("\nDifferences detected. Check the indentation of your new file.")

if __name__ == "__main__":
    run_audit()
