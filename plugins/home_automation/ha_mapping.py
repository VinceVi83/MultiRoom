from abc import ABC, abstractmethod
from rapidfuzz import fuzz
from config_loader import cfg
import logging
logger = logging.getLogger(__name__)

class BaseEntity(ABC):
    """Base Entity for Home Automation devices
    
    Role: Abstract base class for all HA device entities.
    
    Methods:
        __init__(self, data, service) : Initialize entity with data and service.
    """
    def __init__(self, data, service):
        self.id = data['id']
        self.name = data.get('name', self.id)
        self.service = service


class DeviceCollection(ABC):
    """Device collection for managing lights and switches
    
    Role: Manages inventory and search functionality for HA devices.
    
    Methods:
        __init__(self, json_data=None, service=None) : Initialize collection with optional data.
        _initialize(self, data) : Parse and categorize devices from JSON data.
        list_inventory(self) : Print formatted inventory of all devices.
        similarity(self, a, b) : Calculate similarity score between two strings.
        search(self, query_name, device_type) : Search for matching device by name.
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
        logger.info(f"\n{'CATEGORY':<12} | {'NAME':<30} | {'ID'}")
        logger.info("-" * 80)
        for l in self.lights:
            logger.info(f"{'Light':<12} | {l.name:<30} | {l.id}")
        for s in self.switches:
            logger.info(f"{'Switch':<12} | {s.name:<30} | {s.id}")

    def similarity(self, a, b):
        return fuzz.token_set_ratio(a.lower(), b.lower())

    def _process_name_for_search(self, name):
        return name.lower().replace("_", " ").replace("light", "").strip()

    def search(self, query_name, device_type):
        pool = self.lights if device_type == "LIGHT" else self.switches
        
        best_match = None
        highest_score = 0
        threshold = 70

        query_clean = query_name.lower().strip()

        for device in pool:
            name_processed = self._process_name_for_search(device.name)
            score = fuzz.token_set_ratio(query_clean, name_processed)
            
            if score > highest_score and score >= threshold:
                highest_score = score
                best_match = device

        if best_match:
            logger.info(f"   [Match] '{query_name}' -> '{best_match.name}' ({highest_score}%)")
        return best_match


class LightEntity(BaseEntity):
    """Light device entity for Home Automation
    
    Role: Controls light devices including state, brightness, and toggling.
    
    Methods:
        get_state(self) : Get current state of the light.
        get_current_brightness(self) : Get current brightness as percentage.
        turn_on(self) : Turn the light on.
        turn_off(self) : Turn the light off.
        toggle(self) : Toggle the light on/off.
        set_brightness_percent(self, percent: int) : Set brightness to percentage.
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
    
    def toggle(self):
        return self.service.call_action("light", "toggle", self.id)

    def set_brightness_percent(self, percent: int):
        data = {"brightness_pct": min(max(percent, 0), 100)}
        return self.service.call_action("light", "turn_on", self.id, data=data)


class SwitchEntity(BaseEntity):
    """Switch device entity for Home Automation
    
    Role: Controls switch devices including on/off and toggle operations.
    
    Methods:
        turn_on(self) : Turn the switch on.
        turn_off(self) : Turn the switch off.
        toggle(self) : Toggle the switch on/off.
    """
    def turn_on(self):
        return self.service.call_action("switch", "turn_on", self.id)
        
    def turn_off(self):
        return self.service.call_action("switch", "turn_off", self.id)

    def toggle(self):
        return self.service.call_action("switch", "toggle", self.id)
