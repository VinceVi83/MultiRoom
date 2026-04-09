import shutil
import yaml
import argparse
from pathlib import Path
import logging
logger = logging.getLogger(__name__)

def deep_merge_with_placeholder(source, destination):
    for key, value in source.items():
        if isinstance(value, dict):
            node = destination.setdefault(key, {})
            if not isinstance(node, dict):
                destination[key] = value 
            else:
                deep_merge_with_placeholder(value, node)
        else:
            if key not in destination:
                if is_reverse:
                    destination[key] = value
                else:
                    example_val = value if value is not None else ""
                    destination[key] = f"**TO BE COMPLETED** (e.g., {example_val})"
    return destination

def migrate_yaml_pair(source_path, target_path, label):
    if not source_path.exists():
        return
    logger.info(f"[{label}] Currently sync: {source_path.name} -> {target_path.name}")
    if not target_path.exists():
        logger.info(f"[{label}] Creating new file: {target_path.name}")
        shutil.copy(source_path, target_path)
        return

    with open(source_path, 'r', encoding='utf-8') as f:
        source_data = yaml.safe_load(f) or {}
    
    with open(target_path, 'r', encoding='utf-8') as f:
        target_data = yaml.safe_load(f) or {}

    updated_data = deep_merge_with_placeholder(source_data, target_data)

    with open(target_path, 'w', encoding='utf-8') as f:
        yaml.dump(updated_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000)
    
    logger.info(f"[{label}] Sync completed: {source_path.name} -> {target_path.name}")

def run_migration(reverse=False):
    ROOT = Path(__file__).resolve().parent.parent 
    DATA_DIR = Path.home() / "Documents" / "ALISU_DATA"
    
    mode_label = "REVERSE (Data -> Template)" if reverse else "NORMAL (Template -> Data)"
    logger.info(f"--- RUNNING MIGRATION: {mode_label} ---")

    src_global = ROOT / "config_example.yaml"
    dst_global = DATA_DIR / "config.yaml"
    
    if reverse:
        migrate_yaml_pair(dst_global, src_global, "GLOBAL")
    else:
        migrate_yaml_pair(src_global, dst_global, "GLOBAL")

    plugins_base = DATA_DIR / "plugins" if reverse else ROOT / "plugins"
    
    if plugins_base.exists():
        for folder in plugins_base.iterdir():
            if not folder.is_dir() or folder.name.startswith("__"):
                continue
            
            plugin_name = folder.name
            
            if reverse:
                user_cfg = DATA_DIR / "plugins" / plugin_name / "config.yaml"
                tmpl_cfg = ROOT / "plugins" / plugin_name / "config_example.yaml"
                migrate_yaml_pair(user_cfg, tmpl_cfg, f"PLUGIN: {plugin_name}")
            else:
                tmpl_cfg = ROOT / "plugins" / plugin_name / "config_example.yaml"
                user_dir = DATA_DIR / "plugins" / plugin_name
                user_dir.mkdir(parents=True, exist_ok=True)
                user_cfg = user_dir / "config.yaml"
                migrate_yaml_pair(tmpl_cfg, user_cfg, f"PLUGIN: {plugin_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ALISU Configuration Migrator")
    parser.add_argument("-r", "--reverse", action="store_true", help="Sync from User Data back to Templates")
    args = parser.parse_args()
    
    run_migration(reverse=args.reverse)