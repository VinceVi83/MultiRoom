import json
import time
import argparse
import sys
from pathlib import Path

try:
    from tools.hub_messenger import HubMessenger
    from tools.task_context import TaskContext
except ImportError:
    print("[!] Error: Folder 'tools' or required files not found.")
    sys.exit(1)

class HubTester:
    """Hub Testing Automation Framework
    
    Role: Executes and validates test groups against a Hub server.
    
    Methods:
        __init__(self, host="127.0.0.1", user="test", password="test") : Initialize with server credentials.
        _check_success(self, ctx, label) : Validate if server response matches expected label.
        _execute_group(self, group) : Execute a specific group of commands.
        run_interactive_mode(self, test_groups) : Interactive mode to select test groups.
        run_auto_mode(self, test_groups) : Auto mode to run all test groups sequentially.
        _display_global_report(self) : Display formatted final test report.
    """
    def __init__(self, host="127.0.0.1", user="test", password="test"):
        self.messenger = HubMessenger(host=host, user=user, password=password)
        self.all_results = []

    def _check_success(self, ctx, label):
        cat_ok = ctx.category in label
        sub_ok = (ctx.sub_category in label) if ctx.sub_category != 'NONE' else True
        try:
            return_code_ok = "ReturnCode.SUCCESS" in ctx.return_code
        except:
            return False
        return cat_ok and sub_ok and return_code_ok

    def _execute_group(self, group):
        label = group.get('expected', 'Unknown')
        commands = group.get('ordre', [])
        group_contexts = []

        print(f"\n>>> GROUP: {label}")
        
        for cmd in commands:
            clean_cmd = cmd.replace('test:', '')
            print(f"[*] Sending: {clean_cmd[:40]:<40}", end="\r")
            time.sleep(1)
            start_time = time.perf_counter()
            try:
                response = self.messenger.send_stt(clean_cmd, wait_response=True)
                ctx = TaskContext.from_json(response) if response else TaskContext(clean_cmd)
            except Exception as e:
                ctx = TaskContext(clean_cmd)
                ctx.result = f"ERROR: {str(e)}"
            
            ctx.time = time.perf_counter() - start_time
            group_contexts.append(ctx)

            status = "[OK]" if self._check_success(ctx, label) else "[KO]"
            print(f"{status} {clean_cmd[:40]:<40} ({ctx.time:.2f}s)")
            time.sleep(0.2)

        self.all_results.append({'label': label, 'contexts': group_contexts})

    def run_interactive_mode(self, test_groups):
        while True:
            print(f"\n{'='*10} TEST LIST {'='*10}")
            for i, group in enumerate(test_groups, 1):
                print(f"[{i}] {group.get('expected', 'Unnamed')}")
            print(f"{'='*32}")
            
            choice = input('\nSelect a number (or [Q] to quit, [A] to run all) : ').strip().lower()

            if choice == 'q': break
            if choice == 'a':
                self.run_auto_mode(test_groups)
                break

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(test_groups):
                    self.all_results = []
                    self._execute_group(test_groups[idx])
                    self._display_global_report()
                else:
                    print("[!] Index out of bounds.")
            except ValueError:
                print("[!] Invalid input.")

    def run_auto_mode(self, test_groups):
        print(f"\nAUTO RUN ({len(test_groups)} groups)")
        for group in test_groups:
            self._execute_group(group)
        self._display_global_report()

    def _display_global_report(self):
        total_queries = 0
        total_success = 0
        failed_list = []
        total_time = 0

        print(f"\n\n{'#'*60}\n{' '*15} GLOBAL SERVER REPORT\n{'#'*60}")

        for group in self.all_results:
            label = group['label']
            for ctx in group['contexts']:
                total_queries += 1
                total_time += ctx.time
                if self._check_success(ctx, label):
                    total_success += 1
                else:
                    failed_list.append((label, ctx))

        if failed_list:
            print(f"\nFAILURES ({len(failed_list)}):")
            for label, ctx in failed_list:
                print(f"  - Expected: {label} | Received: {ctx.category} {ctx.sub_category} (Query: {ctx.user_input})")

        rate = (total_success / total_queries * 100) if total_queries > 0 else 0
        print(f"\n{'='*60}")
        print(f"FINAL SCORE   : {total_success}/{total_queries} ({rate:.2f}%)")
        print(f"TOTAL TIME    : {total_time:.2f}s")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str, help="Test JSON file")
    parser.add_argument("-a", "--auto", action="store_true", help="Auto mode")
    parser.add_argument("-r", "--rpi", action="store_true", help="RPI test")
    parser.add_argument("--user", default="test")
    parser.add_argument("--passw", default="test")
    args = parser.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)
        
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if args.rpi:
        tester = HubTester(host="192.168.0.35", user=args.user, password=args.passw)
    else:
        tester = HubTester(user=args.user, password=args.passw)

    if args.auto:
        tester.run_auto_mode(data)
    else:
        tester.run_interactive_mode(data)
