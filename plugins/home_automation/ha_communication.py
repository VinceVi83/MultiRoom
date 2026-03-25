import requests
import json
import os
from config_loader import cfg
from plugins.home_automation.ha_mapping import DeviceCollection


class CommunicationHA:
    """Home Assistant Service Plugin
    
    Role: Manages Home Assistant interactions including device control, light toggling, brightness management, and command handling.
    
    Methods:
        __new__(cls, *args, **kwargs) : Singleton pattern for instance creation.
        __init__() : Initialize service with URL, headers, and device registry.
        call_action(domain, service, entity_id, data=None) : Call action on Home Assistant entity.
        smart_toggle(action) : Toggle lights based on current state.
        set_brightness_percent_all(level_percent) : Set brightness for all lights.
        handle_request(context) : Execute command based on label and context.
        get_state(entity_id) : Retrieve state of specific entity.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(CommunicationHA, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.url = f"http://{cfg.home_automation.HA_HOSTNAME}:8123/api"
            self.headers = {
                "Authorization": f"Bearer {cfg.home_automation.HA_TOKEN}",
                "Content-Type": "application/json"
            }
            self.initialized = True

            registry_file = os.path.join(cfg.home_automation.DATA_DIR, "ha_actuators.json")
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

            return cfg.RETURN_CODE.ERR

        except Exception as e:
            return cfg.RETURN_CODE.ERR_NOT_CONNECTED

    def smart_toggle(self, action):
        my_entity_ids = [l.id for l in self.devices.lights]
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
        all_ids = [l.id for l in self.devices.lights]

        if brightness_255 > 0:
            return self.call_action("light", "turn_on", all_ids, data=data)
        return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def handle_request(self, context):
        if context.location == "NONSENSE":
            return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

        try:
            params = dict(item.split(":") for item in context.label.split(","))
            device_type = params.get("TYPE", "")
            action = params.get("ACTION", "")

            if context.location == "ALL" and device_type == "LIGHT":
                if action == "ON":
                    return self.smart_toggle(action)
                elif action == "OFF":
                    return self.smart_toggle(action)
                return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

            target = self.devices.search(context.location, device_type)
            if not target:
                return cfg.RETURN_CODE.ERR_UNKNOWN_DEVICE
            if action == "OFF":
                return target.turn_off()
            elif action == "ON":
                return target.turn_on()
            elif action == "TOOGLE":
                return target.toggle()
            elif action == "NIGHT_MODE":
                return self.devices.set_brightness_percent_all(5)
            elif action == "DAY_MODE":
                return self.devices.set_brightness_percent_all(100)
            return cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

        except Exception as e:
            return cfg.RETURN_CODE.ERR

    def get_state(self, entity_id):
        try:
            response = requests.get(f"{self.url}/states/{entity_id}", headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return None
