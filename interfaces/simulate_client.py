import os
import json
import time
import argparse
import sys
from pathlib import Path
from config_loader import cfg
from tools.hub_messenger import HubMessenger
from tools.task_context import TaskContext


class STTClientSimulator:
    """STTClientSimulator
    
    Role: Simulates STT/PTT client behavior using HubMessenger for sending and HTTPS synchronous server.
    
    Methods:
        __init__(self, path, mode, host="127.0.0.1", user="test", password="test") : Initialize simulator with JSON path, mode, and optional certificate.
        load_and_verify(self) : Load JSON file and verify audio files in PTT mode.
        check_result(self, response) : Verify if Hub response is correct using TaskContext.
        display_mismatch(self, context, exp, item_idx) : Display mismatch details for failed tests.
        send_to_hub(self, entry) : Send a JSON entry to Hub via Messenger.
        interactive_mode(self) : Manual interactive testing mode.
        auto_mode(self) : Automatic sequential testing mode.
        show_final_summary(self) : Display final test summary statistics.
    """
    def __init__(self, path, mode, host="127.0.0.1", user="test", password="test"):
        self.messenger = HubMessenger(user=user, password=password)
        self.json_path = Path(path)
        self.mode = mode
        self.records = []
        self.current_idx = 0
        self.current_object = None
        
        self.stats = {
            "total": 0, 
            "success": 0, 
            "errors": 0,
            "to_verify": 0,
            "failed_ids": [],
            "verify_ids": []
        }
        
        try:
            self.load_and_verify()
        except Exception as e:
            print(f"Failed to initialize simulator: {e}")
            sys.exit(1)

    def load_and_verify(self):
        if not self.json_path.exists():
            print(f"File not found: {self.json_path}")
            sys.exit(1)
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.records = json.load(f)
        self.stats["total"] = len(self.records)

    def display_mismatch(self, context, exp, item_idx, is_verify=False):
        sep = "─" * 90
        status_label = "TO VERIFY (Subtle Diff)" if is_verify else "MISMATCH DETECTED"
        header = f"{'TYPE':<12} | {'CATEGORY':<15} | {'SUBCAT':<15} | {'LOC':<15} | {'CODE':<15} | {'RES'}"
        
        print(f"\n{status_label} on item #{item_idx}: '{context.user_input}'")
        print(sep)
        print(header)
        print(sep)
        print(f"{'OBTAINED':<12} | {context.category:<15} | {context.sub_category:<15} | {context.location:<15} | {context.return_code:<15} | {context.result}")
        print(f"{'EXPECTED':<12} | {exp.get('Category'):<15} | {exp.get('Subcategory'):<15} | {exp.get('Location'):<15} | {exp.get('ReturnCode'):<15} | {exp.get('Result')}")
        print(sep)

    def check_result(self, response):
        if not response or not self.current_object:
            self.stats["errors"] += 1
            self.stats["failed_ids"].append((self.current_idx, None, self.current_object))
            return False

        try:
            context = TaskContext.from_json(response)
            exp = self.current_object

            data_match = (
                context.category == exp.get('Category') and
                context.sub_category == exp.get('Subcategory') and
                str(context.return_code) == str(exp.get('ReturnCode'))
            )

            has_subtle_diff = (
                context.location.lower() != exp.get('Location', '').lower() or
                context.result.lower() != exp.get('Result', '').lower()
            )

            if data_match:
                if has_subtle_diff:
                    self.stats["to_verify"] += 1
                    self.stats["verify_ids"].append((self.current_idx, context, exp))
                    print(f"[#{self.current_idx}] TO VERIFY: {context.category} (Subtle diff)")
                else:
                    print(f"[#{self.current_idx}] OK: {context.category} | {context.sub_category}")
                    self.stats["success"] += 1
                return True
            else:
                print(f"[#{self.current_idx}] MISMATCH: {context.category} vs {exp.get('Category')}")
                self.stats["errors"] += 1
                self.stats["failed_ids"].append((self.current_idx, context, exp))
                return False
        except Exception as e:
            print(f"   [!] Error check_result: {e}")
            self.stats["errors"] += 1
            return False

    def send_to_hub(self, entry):
        self.current_object = entry
        print(f"\n[*] Test [{self.current_idx + 1}/{len(self.records)}]: {entry.get('Command', 'Audio PTT')}")

        if self.mode == "ptt":
            audio_path = self.json_path.parent / entry.get('audio_path')
            self.messenger.send_ptt(str(audio_path))
        else:
            try:
                response = self.messenger.send_stt(entry['Command'], wait_response=True)
                self.check_result(response)
            except Exception as e:
                print(f"   [!] STT send failed: {e}")
                self.stats["errors"] += 1
                self.stats["failed_ids"].append(self.current_idx)

    def show_final_summary(self):
        sep_double = "═" * 95
        sep_simple = "─" * 95

        print(f"\n{sep_double}")
        print(f"RESULTS REVIEW PHASE")
        print(f"{sep_double}")

        if self.stats["verify_ids"]:
            print(f"\n[SECTION 1/2] ITEMS TO VERIFY ({len(self.stats['verify_ids'])} items)")
            for idx, ctx, exp in self.stats["verify_ids"]:
                self.display_mismatch(ctx, exp, idx, is_verify=True)
                time.sleep(0.1)

        if self.stats["failed_ids"]:
            print(f"\n[SECTION 2/2] CRITICAL FAILURES ({len(self.stats['failed_ids'])} items)")
            print("These items have errors in category, subcategory, or return code.")
            for idx, ctx, exp in self.stats["failed_ids"]:
                if ctx:
                    self.display_mismatch(ctx, exp, idx, is_verify=False)
                else:
                    print(f"\n[!] ID #{idx}: No context received (Server error or timeout)")
                time.sleep(0.1)

        sep_stats = "=" * 40
        print(f"\n{sep_stats}")
        print(f"       FINAL TEST SUMMARY")
        print(sep_stats)
        print(f"  Total         : {self.stats['total']}")
        print(f"  Success       : {self.stats['success']}")
        print(f"  To Verify     : {self.stats['to_verify']}")
        print(f"  Failed        : {self.stats['errors']}")
        
        if self.stats['total'] > 0:
            ratio = ((self.stats['success'] + self.stats['to_verify']) / self.stats['total']) * 100
            print(f"  Pass Rate     : {ratio:.1f}%")
        print(f"{sep_stats}\n")

    def interactive_mode(self):
        while True:
            prompt = f"ID [{self.current_idx}/{len(self.records)-1}] (n=next / q=quit / ID) > "
            choice = input(prompt).strip().lower()
            if choice == 'q': break
            if choice in ('n', ''):
                if self.current_idx < len(self.records):
                    self.send_to_hub(self.records[self.current_idx])
                    self.current_idx += 1
                continue
            if choice.isdigit():
                idx = int(choice)
                if 0 <= idx < len(self.records):
                    self.current_idx = idx
                    self.send_to_hub(self.records[self.current_idx])
                else:
                    print(f"   [!] Out of range: {idx}")
            else:
                print("   [!] Invalid input (use 'n', 'q', or a numeric ID)")

    def auto_mode(self):
        for i, entry in enumerate(self.records):
            self.current_idx = i
            self.send_to_hub(entry)
            if self.mode == "stt": time.sleep(1)
        self.show_final_summary()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="Path to JSON file")
    parser.add_argument("-m", "--mode", choices=['stt', 'ptt'], required=True)
    parser.add_argument("-i", "--interactive", action="store_true")
    parser.add_argument("-c", "--cert", help="Path to cert.pem")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="test")
    
    args = parser.parse_args()
    sim = STTClientSimulator(args.path, args.mode, args.cert, args.user, args.password)
    
    if args.interactive:
        sim.interactive_mode()
        sim.show_final_summary()
    else:
        sim.auto_mode()
