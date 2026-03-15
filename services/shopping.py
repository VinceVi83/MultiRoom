import os
import json
from tools.mailer_proton import send_mail
from pathlib import Path
from config_loader import cfg


class ShoppingService:
    """
    Shopping list management service (Singleton).

    Main methods:
    - update_shopping_list(result): Adds new unique items to the list.
    - delete_shopping_list(): Deletes the shopping list file permanently.
    - report_shopping_list(): Retrieves the raw list of items (format list).
    - mail_shopping_list(): Formats the list and sends it to the configured email address.
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
        self.file_path = Path(cfg.DIR_DOCS) / "shopping_list.json"
        self._initialized = True

    def _ensure_file_exists(self):
        """Create the file with an empty structure if it does not exist."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({'items': []}, f)



    def update_shopping_list(self, result):
        """Add unique items to the list."""
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
        """Delete the shopping list file."""
        if self.file_path.exists():
            os.remove(self.file_path)
            return True
        return False

    def report_shopping_list(self):
        """Return the list as text or None."""
        if not self.file_path.exists():
            return None

        with open(self.file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data.get('items', [])

    def mail_shopping_list(self):
        """Send the list via email."""
        items = self.report_shopping_list()
        if not items:
            return "The list is empty, nothing to send."

        body = "Here is your shopping list:\n- " + "\n- ".join(items)

        success = send_mail(
            subject="Shopping List",
            body=body,
            to_email=f"course@{cfg.DOMAIN}"
        )
        return "Email sent successfully" if success else "Failed to send email"

