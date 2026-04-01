import os
from pathlib import Path
from plugins.agenda.mailer_proton import MailerProton
from config_loader import cfg
from tools.utils import SimpleStore

class ShoppingService:
    """Shopping Service Plugin
    
    Role: Manages shopping list operations including updates, deletion, reporting, and email notifications.
    
    Methods:
        __new__(cls) : Singleton pattern implementation.
        __init__(self) : Initialize the service with store and mailer.
        update_shopping_list(self, result) : Add new items to the shopping list.
        delete_shopping_list(self) : Delete/clear the shopping list.
        report_shopping_list(self) : Get current shopping list items.
        mail_shopping_list(self) : Send shopping list via email.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ShoppingService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, cfg):
        if self._initialized:
            return
        self.cfg = cfg
        file_path = Path(self.cfg.daily.DATA_DIR) / "shopping_list.json"
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
            return self.cfg.RETURN_CODE.SUCCESS_NOTHING_TO_DO

        body = "Here is your shopping list:\n- " + "\n- ".join(items)
        success = self.mailer_proton.send_mail(
            subject="Shopping List",
            body=body,
            to_email=f"system@{cfg.agenda.mail_server.DOMAIN}" # TODO internal request callback
        )
        return self.cfg.RETURN_CODE.SUCCESS if success else self.cfg.RETURN_CODE.ERR

if __name__ == "__main__":
    shopping = ShoppingService()
    print(shopping.report_shopping_list())
