import requests
import json
import os
from dataclasses import dataclass
from typing import Optional
from plugins.home_automation.ha_mapping import DeviceCollection
import logging
logger = logging.getLogger(__name__)

@dataclass
class HAAction:
    type: str = "NONE"
    action: str = "NONE"

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            type=str(data.get("TYPE", "NONE")).upper(),
            action=str(data.get("ACTION", "NONE")).upper(),
        )

    @classmethod
    def from_json(cls, raw: str):
        return cls.from_dict(json.loads(raw))

    @classmethod
    def from_native(cls, sub_category: str):
        if not sub_category:
            return cls()

        s = sub_category.strip()
        if "," in s:
            try:
                data = {
                    k.strip().upper(): v.strip().upper()
                    for k, v in (item.split(":", 1) for item in s.split(",") if ":" in item)
                }
                return cls.from_dict(data)
            except Exception:
                return cls()
        if ":" in s:
            device_type, action = s.split(":", 1)
            return cls(type=device_type.strip().upper(), action=action.strip().upper())
        return cls()

    @property
    def label(self) -> str:
        return f"{self.type}:{self.action}"

class CommunicationHA:
    """Home Assistant Service Plugin
    
    Role: Manages Home Assistant API interactions and device control.
    
    Methods:
        __new__(cls, *args, **kwargs) : Singleton pattern implementation.
        __init__(self, cfg) : Initialize connection and load device registry.
        call_action(self, domain, service, entity_id, data=None) : Send commands to Home Assistant services.
        smart_toggle(self, action) : Toggle lights based on current state.
        set_brightness_percent_all(self, level_percent) : Set brightness for all lights.
        handle_request(self, context) : Process context requests.
        get_state(self, entity_id) : Get state of an entity.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            try:
                cls._instance = super(CommunicationHA, cls).__new__(cls)
                cls._instance._ready_flag = False 
            except Exception as e:
                logger.error(f"[CRITICAL] Failed to create CommunicationHA instance: {e}")
                return None
        return cls._instance

    def __init__(self, cfg):
        if getattr(self, '_ready_flag', False):
            return
            
        self.cfg = cfg
        self.url = f"http://{self.cfg.ha_config.HA_HOSTNAME}:8123/api"
        self.headers = {
            "Authorization": f"Bearer {self.cfg.ha_config.HA_TOKEN}",
            "Content-Type": "application/json"
        }
        registry_file = os.path.join(self.cfg.config_dir, "ha_actuators.json")
        try:
            if os.path.exists(registry_file):
                with open(registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.devices = DeviceCollection(data, self)
                self._ready_flag = True
            else:
                logger.info(f"[!] Registry file missing: {registry_file}")
        except Exception as e:
            logger.error(f"[!] Error initializing devices: {e}")

    def call_action(self, domain, service, entity_id, data=None):
        endpoint = f"{self.url}/services/{domain}/{service}"
        ids = [entity_id] if isinstance(entity_id, str) else entity_id
        payload = {"entity_id": ids}
        if data:
            payload.update(data)
        try:
            res = requests.post(endpoint, headers=self.headers, json=payload, timeout=10)
            if res.ok:
                return self.cfg.RETURN_CODE.SUCCESS
            return self.cfg.RETURN_CODE.ERR

        except requests.exceptions.Timeout:
            return self.cfg.RETURN_CODE.ERR_NOT_CONNECTED
        except requests.exceptions.ConnectionError:
            return self.cfg.RETURN_CODE.ERR_NOT_CONNECTED
        except Exception:
            return self.cfg.RETURN_CODE.ERR

    def smart_toggle(self, action):
        my_entity_ids = [l.id for l in self.devices.lights]
        try:
            response = requests.get(f"{self.url}/states", headers=self.headers, timeout=10)
            response.raise_for_status()
            all_states = response.json()
        except Exception:
            return self.cfg.RETURN_CODE.ERR_NOT_CONNECTED

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
        return self.cfg.RETURN_CODE.SUCCESS_NOTHING_TO_DO

    def set_brightness_percent_all(self, level_percent):
        brightness_255 = int((level_percent / 100) * 255)
        data = {"brightness": brightness_255}
        all_ids = [l.id for l in self.devices.lights]

        if brightness_255 > 0:
            return self.call_action("light", "turn_on", all_ids, data=data)
        return self.cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def _handle_global_light(self, cmd_action: str):
        if cmd_action in ("ON", "OFF"):
            return self.smart_toggle(cmd_action)
        return self.cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def handle_request(self, context, action: HAAction):
        if context.location == "NONSENSE":
            return self.cfg.RETURN_CODE.ERR_INVALID_ARGUMENT
        device_type = action.type.upper()
        cmd_action = action.action.upper()

        try:
            if context.location == "ALL" and device_type == "LIGHT":
                return self._handle_global_light(cmd_action)

            target = self.devices.search(context.location, device_type)
            if not target:
                return self.cfg.RETURN_CODE.ERR_UNKNOWN_DEVICE
            return self._dispatch_device_action(target, cmd_action, device_type)

        except Exception as e:
            logger.error(f"[!] CommunicationHA handle_request error: {e}")
            return self.cfg.RETURN_CODE.ERR
    
    def _dispatch_device_action(self, target, cmd_action: str, device_type: str):
        if cmd_action in ("ON", "OFF", "TOGGLE"):
            try:
                return {
                    "ON": target.turn_on,
                    "OFF": target.turn_off,
                    "TOGGLE": target.toggle,
                }[cmd_action]()
            except Exception as e:
                logger.error(f"Error executing '{cmd_action}' on device: {e}")
                return self.cfg.RETURN_CODE.ERR
        if device_type == "LIGHT":
            if cmd_action == "NIGHT_MODE":
                return target.set_brightness(5)
            if cmd_action == "DAY_MODE":
                return target.set_brightness(100)
        logger.warning(f"Action '{cmd_action}' not supported for device type '{device_type}'")
        return self.cfg.RETURN_CODE.ERR_INVALID_ARGUMENT

    def get_state(self, entity_id):
        try:
            response = requests.get(f"{self.url}/states/{entity_id}", headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
