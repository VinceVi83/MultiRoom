import requests
import json
import os

class HomeAutomationRegistry:
    """Home Automation Entity Registry
    
    Role: Manages Home Assistant device synchronization including actuators, buttons, and battery monitoring with validation and filtering.
    
    Methods:
        __init__(self) : Initialize the service with configuration parameters.
        _fetch_ha_data(self) : Fetch raw data from Home Assistant API (states and services).
        _safe_load_json(self, filename) : Load JSON file safely with error handling.
        _safe_save_json(self, data, filename) : Save JSON file with proper formatting.
        _is_valid_actuator(self, eid, name) : Determine if an actuator should be kept or ignored.
        sync_actuators(self) : Synchronize actuators with filtering via _is_valid_actuator.
        sync_button_mapping(self) : Synchronize button mapping without overwriting manual config.
        sync_batteries(self) : Generate battery status report for all devices.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.url = f"http://{self.cfg.ha_config.HA_HOSTNAME}:8123/api"
        self.headers = {
            "Authorization": f"Bearer {self.cfg.ha_config.HA_TOKEN}",
            "Content-Type": "application/json"
        }

        self.global_blacklist = [
            "_info", "_identify", "_restart", "_update", "backup", 
            "connectivity", "battery", "update_available"
        ]

        self.actuator_blacklist = [
            "indicator", "locked", "delay", "protection", 
            "power_limit", "status", "night_light"
        ]
        
        self.button_blacklist = ["yeelink", "yeelight", "toggle"]

        self.model_strict_suffixes = {
            "cuco": "_switch",
            "purifier": "_switch"
        }

        self.black_actions = [
            "completed", "failed", "in_progress", 
            "unavailable", "unknown", "none"
        ]

    def _fetch_ha_data(self):
        try:
            states = requests.get(f"{self.url}/states", headers=self.headers, timeout=10).json()
            services = requests.get(f"{self.url}/services", headers=self.headers, timeout=10).json()
            return states, services
        except Exception as e:
            print(f"Network error HA: {e}")
            return None, None

    def _safe_load_json(self, filename):
        path = os.path.join(self.cfg.DATA_DIR, filename)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                print(f"Error reading {filename}, reset.")
        return {}

    def _safe_save_json(self, data, filename):
        path = os.path.join(self.cfg.DATA_DIR, filename)
        with open(path, "w", encoding="utf-8", newline='\n') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _is_valid_actuator(self, eid, name):
        eid_low = eid.lower()
        name_low = name.lower()

        combined_blacklist = self.global_blacklist + self.actuator_blacklist
        if any(kw in eid_low or kw in name_low for kw in combined_blacklist):
            return False

        for model_key, suffix in self.model_strict_suffixes.items():
            if model_key in eid_low:
                return eid_low.endswith(suffix)

        return True

    def sync_actuators(self):
        states, services = self._fetch_ha_data()
        if not states: return 0
        
        domain_actions = {d['domain']: list(d['services'].keys()) for d in services}
        inventory = []

        for s in states:
            eid = s['entity_id']
            domain = eid.split('.')[0]
            
            if domain in ["light", "switch", "remote"] and s.get('state') != "unavailable":
                friendly_name = s.get('attributes', {}).get('friendly_name', eid)

                if not self._is_valid_actuator(eid, friendly_name):
                    continue

                inventory.append({
                    "id": eid,
                    "name": friendly_name,
                    "domain": domain,
                    "state": s.get('state'),
                    "actions": domain_actions.get(domain, []),
                    "params": {"brightness_pct": {"min": 0, "max": 100}} if domain == "light" else {}
                })
        
        self._safe_save_json(inventory, "ha_actuators.json")
        return len(inventory)

    def sync_button_mapping(self):
        states, _ = self._fetch_ha_data()
        if not states: return 0

        mapping_file = "ha_action_mapping.json"
        current_mapping = self._safe_load_json(mapping_file)
        new_mapping = {}
        added = 0

        for s in states:
            eid = s['entity_id'].lower()
            domain = eid.split('.')[0]
            if domain not in ["event", "button"]: continue
            
            attr = s.get('attributes', {})
            name = attr.get('friendly_name', eid)

            if any(kw in eid or kw in name.lower() for kw in self.global_blacklist + self.button_blacklist):
                continue
            
            event_types = attr.get('event_types', ["single", "double", "hold"])
            clean_actions = [a for a in event_types if a not in self.black_actions]
            if not clean_actions: continue

            if eid in current_mapping:
                new_mapping[eid] = current_mapping[eid]
                for a in clean_actions:
                    if a not in new_mapping[eid]["actions"]:
                        new_mapping[eid]["actions"][a] = "NEW ACTION DETECTED"
            else:
                new_mapping[eid] = {
                    "name": name,
                    "actions": {a: "TO BE CONFIGURED" for a in clean_actions}
                }
                added += 1

        self._safe_save_json(new_mapping, mapping_file)
        return added

    def sync_batteries(self):
        states, _ = self._fetch_ha_data()
        if not states: return 0

        report = {}
        for s in states:
            eid = s['entity_id'].lower()
            attr = s.get('attributes', {})
            
            if attr.get('device_class') == 'battery' or '_battery' in eid:
                name = attr.get('friendly_name', s['entity_id'])
                val = s.get('state')
                
                try:
                    level = int(float(val))
                    report[name] = f"{level}%"
                except (ValueError, TypeError):
                    continue

        self._safe_save_json(report, "ha_battery_status.json")
        return len(report)
    
    def update_device(self):
        self.sync_actuators()
        self.sync_button_mapping()
        self.sync_batteries()

if __name__ == "__main__":
    reg = HomeAutomationRegistry()
    print(f"Actuators: {reg.sync_actuators()}")
    print(f"Buttons: {reg.sync_button_mapping()}")
    print(f"Batteries: {reg.sync_batteries()}")
