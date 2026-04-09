import yaml
import os
import logging
logger = logging.getLogger(__name__)

OLD_YAML = "agents_config.yaml"
NEW_YAML = "agents_config_new.yaml"

def get_yaml_structure(filepath):
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
        logger.error(f"reading {filepath}: {e}")
        return None

def run_audit():
    old_struct = get_yaml_structure(OLD_YAML)
    new_struct = get_yaml_structure(NEW_YAML)

    if old_struct is None or new_struct is None:
        logger.info("Cannot compare: one of the files is missing or invalid.")
        return

    old_sections = set(old_struct.keys())
    new_sections = set(new_struct.keys())

    missing_sections = old_sections - new_sections
    extra_sections = new_sections - old_sections

    if not missing_sections and not extra_sections:
        logger.info("All sections match.")
    else:
        for s in missing_sections:
            logger.info(f"Missing section: {s}")
        for s in extra_sections:
            logger.info(f"New section: {s}")

    common_sections = old_sections & new_sections
    for section in common_sections:
        old_agents = old_struct[section]
        new_agents = new_struct[section]

        missing_agents = old_agents - new_agents
        extra_agents = new_agents - old_agents

        if missing_agents or extra_agents:
            logger.info(f"--- Section: {section} ---")
            for a in missing_agents:
                logger.info(f"Missing agent: {a}")
            for a in extra_agents:
                logger.info(f"New agent: {a}")

    has_error = False
    if not missing_sections and not extra_sections:
        has_error = False
    else:
        has_error = True

    if not has_error:
        logger.info("Structure is identical (or increased)! Migration is safe.")
    else:
        logger.info("Differences detected. Check the indentation of your new file.")

if __name__ == "__main__":
    run_audit()
