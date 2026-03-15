import requests
import json
import os
from config_loader import cfg
from tools.ha_entities import DeviceCollection


class HAService:
    """Home Assistant Service - Manages interactions with Home Assistant.

    Methods:
        __new__(cls, *args, **kwargs) : Singleton pattern to ensure only one instance of HAService.
        __init__() : Initializes the service with the necessary URL and headers.
        call_action(domain, service, entity_id, data=None) : Calls an action on a Home Assistant entity.
        smart_toggle(action) : Toggles lights based on current state.
        set_brightness_percent_all(level_percent) : Sets brightness level for all lights.
        handle_request(raw_data, location) : Interprets and executes a command based on raw data and location.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HAService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.url = f"http://{cfg.HA_HOSTNAME}:8123/api"
            self.headers = {
                "Authorization": f"Bearer {cfg.HA_TOKEN}",
                "Content-Type": "application/json"
            }
            self.initialized = True

            registry_file = os.path.join(cfg.DIR_DOCS, "ha_device_list.json")
            with open(registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.devices = DeviceCollection(data, self)

    def call_action(self, domain, service, entity_id, data=None):
        endpoint = f"{self.url}/services/{domain}/{service}"
        ids = [entity_id] if isinstance(entity_id, str) else entity_id
        payload = {"entity_id": ids}
        if data:
            payload.update(data)
        try:
            res = requests.post(endpoint, headers=self.headers, json=payload)

            if res.ok:
                return cfg.RETURN_CODE.SUCCESS

            print(f"[-] HA Error {res.status_code}: {res.text}")
            return cfg.RETURN_CODE.ERR

        except Exception as e:
            print(f"[-] Connection Error: {e}")
            return cfg.RETURN_CODE.ERR_NOT_CONNECTED

    def smart_toggle(self, action):
        my_entity_ids = [l.entity_id for l in self.lights]
        response = requests.get(f"{self.url}/states", headers=self.headers)
        all_states = response.json()
        lights_on = []
        lights_off = []

        for item in all_states:
            eid = item['entity_id']
            if eid in my_entity_ids:
                if item['state'] == 'on':
                    lights_on.append(eid)
                else:
                    lights_off.append(eid)

        if lights_on and action == "OFF":
            return self.call_action("light", "toggle", lights_on)
        elif lights_off and action == "ON":
            return self.call_action("light", "toggle", lights_off)

    def set_brightness_percent_all(self, level_percent):
        brightness_255 = int((level_percent / 100) * 255)
        data = {"brightness": brightness_255}
        all_ids = [light.entity_id for light in self.lights]

        if brightness_255 > 0:
            return self.call_action("light", "turn_on", all_ids, data=data)
        return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def handle_request(self, raw_data, location):
        if location == "NONSENSE":
            return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

        try:
            params = dict(item.split(":") for item in raw_data.split(","))
            device_type = params.get("TYPE", "").lower()
            action = params.get("ACTION", "").upper()

            if location == "ALL":
                if action == "ON":
                    return self.smart_toggle(action)
                elif action == "OFF":
                    return self.smart_toggle(action)
                return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

            target = self.devices.search(location, device_type)
            if not target:
                print(f"[!] {device_type} not found at: {location}")
                return cfg.RETURN_CODE.ERR_UNKNOWN_DEVICE
            if action == "OFF":
                return target.turn_off()
            elif action == "ON":
                return target.turn_on()
            elif action == "NIGHT_MODE":
                return self.devices.set_brightness_percent_all(5)
            elif action == "DAY_MODE":
                return self.devices.set_brightness_percent_all(100)

            print(f"[!] Unknown action: {action}")
            return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

        except Exception as e:
            print(f"[!] Error in handle_request: {e}")
            return cfg.RETURN_CODE.ERR

    def get_state(self, entity_id):
        """
        Retrieves the state of a Home Assistant entity.

        Args:
        - entity_id: The ID of the entity.

        Returns:
        - The state of the entity or None if an error occurs.
        """
        try:
            response = requests.get(f"{self.url}/states/{entity_id}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Erreur API (Get State {entity_id}): {e}")
            return None