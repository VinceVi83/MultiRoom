import json
import os
from pathlib import Path
from config_loader import cfg

def main():
    file_path = Path(cfg.DATA_DIR) / "Archive/record.json"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from '{file_path}'.")
        return
    except Exception as e:
        print(f"Error: Unexpected error reading file: {e}")
        return

    to_remove = []
    index = 0
    total = len(data)

    while index < total:
        item = data[index]
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 50)
        if item in to_remove:
            print(">>> MARKED FOR DELETION <<<")
        
        print(f"Input:          {item.get('Command', 'N/A')}")
        print(f"File:           {item.get('audio_path', 'N/A')}")
        print("-" * 50)
        print(f"Location:       {item.get('Location', 'N/A')}")
        print(f"Category:       {item.get('Category', 'N/A')}")
        print(f"Label:          {item.get('Subcategory', 'N/A')}")
        print(f"Result:         {item.get('Result', 'N/A')}")
        print(f"ReturnCode:     {item.get('ReturnCode', 'N/A')}")
        print("=" * 50)
        
        print(f"\n[Item {index + 1} of {total}]")
        print("Controls: [Enter] Next | [p] Previous | [r] Remove/Undo | [q] Quit & Save")
        
        user_input = input(">> ").lower().strip()

        if user_input == '':
            index += 1
        elif user_input == 'p':
            if index > 0:
                index -= 1
        elif user_input == 'r':
            if item in to_remove:
                to_remove.discard(item)
                index += 1
            else:
                to_remove.add(item)
                index += 1
        elif user_input == 'q':
            break

    if to_remove:
        print("\n" + "!" * 20)
        print(f"ITEMS TO BE DELETED ({len(to_remove)}):")
        for i, item in enumerate(to_remove):
            print(f"{i+1}. {item.get('Command')} | {item.get('audio_path')}")
        
        confirm = input("\nConfirm permanent deletion? (y/n): ").lower()
        
        if confirm == 'y':
            new_data = [item for item in data if item not in to_remove]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, indent=4, ensure_ascii=False)
        else:
            pass
    else:
        pass

if __name__ == "__main__":
    main()
