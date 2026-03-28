"""Home Automation Entity Registry Module."""


class HomeAutomationRegistry:
    """Home Automation Entity Registry
    
    Role: Manages home automation entities and devices.
    
    Methods:
        __init__(self) : Initialize registry with empty entity storage.
        register_entity(self, entity_id: str, name: str, device_type: str) -> None : Register a new entity in the registry.
        register_device(self, device_id: str, device_name: str) -> None : Register a new device in the registry.
        get_entity(self, entity_id: str) -> dict | None : Retrieve an entity by its ID.
        get_device(self, device_id: str) -> dict | None : Retrieve a device by its ID.
        list_entities(self) -> list[dict] : Return a list of all registered entities.
        list_devices(self) -> list[dict] : Return a list of all registered devices.
    """

    def __init__(self):
        self.entities = {}
        self.devices = {}

    def register_entity(self, entity_id: str, name: str, device_type: str) -> None:
        self.entities[entity_id] = {
            'name': name,
            'device_type': device_type
        }

    def register_device(self, device_id: str, device_name: str) -> None:
        self.devices[device_id] = {
            'name': device_name
        }

    def get_entity(self, entity_id: str) -> dict | None:
        return self.entities.get(entity_id)

    def get_device(self, device_id: str) -> dict | None:
        return self.devices.get(device_id)

    def list_entities(self) -> list[dict]:
        return list(self.entities.values())

    def list_devices(self) -> list[dict]:
        return list(self.devices.values())


def create_registry() -> HomeAutomationRegistry:
    """Create and return a new registry instance.

    Returns:
        A new HomeAutomationRegistry instance.
    """
    return HomeAutomationRegistry()
