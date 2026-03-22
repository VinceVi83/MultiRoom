import os
from pathlib import Path
from plugins.agenda.mailer_proton import MailerProton
from config_loader import cfg
from tools.utils import SimpleStore

class ShoppingService:
    """Shopping :A singleton-based service for managing shopping lists with file persistence and email notifications.

    Methods:
        __new__(cls) : Singleton pattern to ensure only one instance of ShoppingService.
        __init__() : Initializes the service with the necessary file path and mailer.
        _ensure_file_exists() : Creates the file with an empty structure if it does not exist.
        update_shopping_list(result) : Adds new unique items to the list.
        delete_shopping_list() : Deletes the shopping list file permanently.
        report_shopping_list() : Retrieves the raw list of items (format list).
        mail_shopping_list() : Formats the list and sends it to the configured email address.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShoppingService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        file_path = Path(cfg.daily.DATA_DIR) / "shopping_list.json"
        self.store = SimpleStore(file_path, default_structure={'items': []})
        self.mailer_proton = MailerProton()
        self._initialized = True

    def update_shopping_list(self, result):
        current_items = self.store.get('items')
        
        new_items = result.get('items', [])
        if isinstance(new_items, str):
            new_items = [i.strip() for i in new_items.split(',') if i.strip()]

        existing_items = set(current_items)
        unique_to_add = [i for i in new_items if i not in existing_items]

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
            return cfg.RETURN_CODE.SUCCESS_NOTHING_TO_DO

        body = "Here is your shopping list:\n- " + "\n- ".join(items)
        success = self.mailer_proton.send_mail(
            subject="Shopping List",
            body=body,
            to_email=f"system@{cfg.agenda.DOMAIN}"
        )
        return cfg.RETURN_CODE.SUCCESS if success else cfg.RETURN_CODE.ERR

if __name__ == "__main__":
    shopping = ShoppingService()
    print(shopping.report_shopping_list())
