import requests
import json
import os
from config_loader import cfg


class HADomoticsCapabilities:
    """Class to interact with Home Assistant for retrieving actionable devices and their capabilities.

    Methods:
        __init__(self) : Initializes the class with the necessary URL and headers.
        get_actionable_devices(self) : Fetches and returns a list of actionable devices.
        _define_params(self, domain, attr) : Defines the min/max bounds for device parameters based on the device type.
    """

    def __init__(self):
        self.url = f"http://{cfg.home_automation.HA_HOSTNAME}:8123/api"
        self.headers = {
            "Authorization": f"Bearer {cfg.home_automation.HA_TOKEN}",
            "Content-Type": "application/json"
        }

    def get_actionable_devices(self):
        try:
            states = requests.get(f"{self.url}/states", headers=self.headers).json()
            services = requests.get(f"{self.url}/services", headers=self.headers).json()
        except Exception as e:
            print(f"Error connecting to Home Assistant: {e}")
            return []

        domain_actions = {d['domain']: list(d['services'].keys()) for d in services}
        inventory = []
        allowed_domains = ["light", "switch"]

        for s in states:
            entity_id = s['entity_id']
            domain = entity_id.split('.')[0]
            state = s.get('state')
            attr = s.get('attributes', {})

            if (domain in allowed_domains and 
                domain in domain_actions and 
                state != "unavailable"):
                
                item = {
                    "id": entity_id,
                    "name": attr.get('friendly_name'),
                    "domain": domain,
                    "state": state,
                    "actions": domain_actions[domain],
                    "limits": self._define_params(domain, attr)
                }
                inventory.append(item)
                
        return inventory

    def _define_params(self, domain, attr):
        limits = {}
        if domain == "light":
            limits["brightness_pct"] = {"min": 0, "max": 100}
        return limits


if __name__ == "__main__":
    registry = HADomoticsCapabilities()
    data = registry.get_actionable_devices()
    output_file = os.path.join(cfg.home_automation.DATA_DIR, "ha_device_list.json")
    
    with open(output_file, "w", encoding="utf-8", newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"HADomoticsCapabilities generated for light and switch in {output_file}")
