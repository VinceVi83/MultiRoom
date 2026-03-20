import os
import json
from plugins.agenda.mailer_proton import MailerProton
from pathlib import Path
from config_loader import cfg

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
        self.file_path = Path(cfg.daily.DATA_DIR) / "shopping_list.json"
        self._initialized = True
        self.mailer_proton = MailerProton()

    def _ensure_file_exists(self):
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({'items': []}, f)

    def update_shopping_list(self, result):
        self._ensure_file_exists()

        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        new_items = result.get('items', [])
        existing_items = set(data['items'])
        unique_to_add = [i for i in new_items if i not in existing_items]

        data['items'].extend(unique_to_add)

        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return unique_to_add

    def delete_shopping_list(self):
        if self.file_path.exists():
            os.remove(self.file_path)
            return cfg.RETURN_CODE.SUCCESS
        return cfg.RETURN_CODE.ERR

    def report_shopping_list(self):
        if not self.file_path.exists():
            return cfg.RETURN_CODE.ERR_MISSING_FILE

        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data.get('items', [])

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
    print("Running shopping service tests...")
    shopping = ShoppingService()
    shopping.mail_shopping_list()
