import requests
import json
import os
from config_loader import cfg

class HADomoticsCapabilities:
    def __init__(self):
        self.url = f"http://{cfg.HA_HOSTNAME}:8123/api"
        self.headers = {
            "Authorization": f"Bearer {cfg.HA_TOKEN}",
            "Content-Type": "application/json"
        }

    def get_actionable_devices(self):
        """Generate the complete dictionary of devices for the LLM"""
        try:
            states = requests.get(f"{self.url}/states", headers=self.headers).json()
            services = requests.get(f"{self.url}/services", headers=self.headers).json()
        except Exception as e:
            print(f"Error connecting to Nagato: {e}")
            return []

        domain_actions = {d['domain']: list(d['services'].keys()) for d in services}
        inventory = []

        for s in states:
            entity_id = s['entity_id']
            domain = entity_id.split('.')[0]
            attr = s.get('attributes', {})
            if domain in domain_actions:
                item = {
                    "id": entity_id,
                    "name": attr.get('friendly_name'),
                    "domain": domain,
                    "state": s['state'],
                    "actions": domain_actions[domain],
                    "limits": self._define_params(domain, attr)
                }
                inventory.append(item)
        return inventory

    def _define_params(self, domain, attr):
        """Defines the min/max bounds according to the device type"""
        limits = {}
        if domain == "light":
            limits["brightness_pct"] = {"min": 0, "max": 100}
        elif domain == "climate":
            limits["temperature"] = {
                "min": attr.get("min_temp", 7),
                "max": attr.get("max_temp", 35)
            }
        elif domain == "cover":
            limits["position"] = {"min": 0, "max": 100}
        return limits

if __name__ == "__main__":
    registry = HADomoticsCapabilities()
    data = registry.get_actionable_devices()
    output_file = os.path.join(cfg.DIR_DOCS, "ha_device_list.json")
    with open(output_file, "w", encoding="utf-8", newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"HADomoticsCapabilities generated in {output_file}")