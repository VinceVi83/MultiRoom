import os
from pathlib import Path
from plugins.agenda.mailer_proton import MailerProton
from config_loader import cfg
from tools.utils import SimpleStore

class ShoppingService:
    """Shopping Service Plugin
    
    Role: Manages shopping list operations including updates, deletion, reporting, and email notifications.
    
    Methods:
        __new__(cls, cfg) : Singleton pattern implementation.
        __init__(self, cfg) : Initialize the service with store and mailer.
        _parse_items(self, items) : Parse comma-separated items into list.
        _get_existing_items(self) : Get current items from store.
        _get_unique_items(self, new_items, existing_items) : Filter unique items to add.
        update_shopping_list(self, result) : Add new items to the shopping list.
        delete_shopping_list(self) : Delete/clear the shopping list.
        report_shopping_list(self) : Get current shopping list items.
        mail_shopping_list_legacy(self) : Send shopping list via email (legacy method).
        mail_shopping_list(self) : Send shopping list via email (new method).
    """
    _instance = None

    def __new__(cls, cfg):
        if cls._instance is None:
            cls._instance = super(ShoppingService, cls).__new__(cls)
            cls._instance._initialized = False
            cls._instance.cfg = cfg
        return cls._instance

    def __init__(self, cfg):
        if self._initialized:
            return
        self.cfg = cfg
        file_path = Path(self.cfg.DATA_DIR) / "shopping_list.json"
        self.store = SimpleStore(file_path, default_structure={'items': []})
        self.mailer_proton = MailerProton()
        self._initialized = True

    def _parse_items(self, items):
        if isinstance(items, str):
            parsed_items = []
            for item in items.split(','):
                item = item.strip()
                if item:
                    parsed_items.append(item)
            return parsed_items
        return items

    def _get_existing_items(self):
        return self.store.get('items')

    def _get_unique_items(self, new_items, existing_items):
        existing_set = set(existing_items)
        unique_items = []
        for item in new_items:
            if item not in existing_set:
                unique_items.append(item)
        return unique_items

    def update_shopping_list(self, result):
        current_items = self._get_existing_items()
        
        new_items = result.get('items', [])
        new_items = self._parse_items(new_items)

        unique_to_add = self._get_unique_items(new_items, current_items)

        if unique_to_add:
            current_items.extend(unique_to_add)
            self.store.update_and_save('items', current_items)
            
        return unique_to_add

    def delete_shopping_list(self):
        return self.store.delete()

    def report_shopping_list(self):
        return self.store.get('items')

    def mail_shopping_list(self):
        items = self.report_shopping_list()
        if not items:
            return None

        body = "Here is your shopping list:\n- " + "\n- ".join(items)
        data = { 
            "internal_api": {
                "plugin": "AGENDA",
                "api_name": "send_mail",
                "subject": "Shopping List",
                "body": body,
                "attachment": None 
            }
        }
        return data

if __name__ == "__main__":
    shopping = ShoppingService()
    print(shopping.report_shopping_list())
