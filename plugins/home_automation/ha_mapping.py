from abc import ABC, abstractmethod
from rapidfuzz import fuzz
from config_loader import cfg


class BaseEntity(ABC):
    """Base class for all entities in Home Assistant.

    Methods:
        __init__(data, service) : Initializes the entity with data and a service.
    """
    def __init__(self, data, service):
        self.id = data['id']
        self.name = data.get('name', self.id)
        self.service = service


class DeviceCollection:
    """Manages collections of devices (lights and switches).

    Methods:
        __init__(json_data=None, service=None) : Initializes the device collection with JSON data and a service.
        _initialize(data) : Populates the collection with devices from JSON data.
        list_inventory() : Lists all devices in the collection.
        similarity(a, b) : Calculates the similarity score between two strings.
        search(query_name, device_type) : Searches for a device by name and type.
    """
    def __init__(self, json_data=None, service=None):
        self.lights = []
        self.switches = []
        self.service = service
        self.initialized = False
        if json_data:
            self._initialize(json_data)

    def _initialize(self, data):
        for item in data:
            domain = item.get('domain')
            if domain == "light":
                self.lights.append(LightEntity(item, self.service))
            elif domain == "switch":
                self.switches.append(SwitchEntity(item, self.service))

        if self.lights or self.switches:
            self.initialized = True

    def list_inventory(self):
        print(f"\n{'CATEGORY':<12} | {'NAME':<30} | {'ID'}")
        print("-" * 80)
        for l in self.lights:
            print(f"{'Light':<12} | {l.name:<30} | {l.id}")
        for s in self.switches:
            print(f"{'Switch':<12} | {s.name:<30} | {s.id}")

    def similarity(self, a, b):
        return fuzz.token_set_ratio(a.lower(), b.lower())

    def search(self, query_name, device_type):
        pool = self.lights if device_type == "light" else self.switches
        
        best_match = None
        highest_score = 0
        threshold = 70

        query_clean = query_name.lower().strip()

        for device in pool:
            name_processed = device.name.lower().replace("_", " ").replace("light", "").strip()
            score = fuzz.token_set_ratio(query_clean, name_processed)
            
            if score > highest_score and score >= threshold:
                highest_score = score
                best_match = device

        if best_match:
            print(f"   [Match] '{query_name}' -> '{best_match.name}' ({highest_score}%)")
        return best_match


class LightEntity(BaseEntity):
    """Represents a light entity in Home Assistant.

    Methods:
        get_state() : Retrieves the current state of the light.
        get_current_brightness() : Retrieves the current brightness level.
        turn_on() : Turns on the light with an optional brightness level.
        turn_off() : Turns off the light.
        set_brightness_percent(percent) : Sets the brightness level of the light.
    """
    def get_state(self):
        state_data = self.service.get_state(self.id)
        return state_data.get('state') if state_data else "unknown"

    def get_current_brightness(self):
        state_data = self.service.get_state(self.id)
        if not state_data or state_data.get('state') == 'off':
            return 0
        
        attrs = state_data.get('attributes', {})
        b255 = attrs.get('brightness', 0)
        return round((b255 / 255) * 100)

    def turn_on(self):
        return self.service.call_action("light", "turn_on", self.id)

    def turn_off(self):
        if self.get_state() == 'on':
            return self.service.call_action("light", "toggle", self.id)
        return cfg.RETURN_CODE.SUCCESS_NOTHING_TO_DO

    def set_brightness_percent(self, percent: int):
        data = {"brightness_pct": min(max(percent, 0), 100)}
        return self.call_action("light", "turn_on", self.id, data=data)


class SwitchEntity(BaseEntity):
    """Represents a switch entity in Home Assistant.

    Methods:
        turn_on() : Turns on the switch.
        turn_off() : Turns off the switch.
    """
    def turn_on(self):
        return self.service.call_action("switch", "turn_on", self.id)
        
    def turn_off(self):
        return self.service.call_action("switch", "turn_off", self.id)
