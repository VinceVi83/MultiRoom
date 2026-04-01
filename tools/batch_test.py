import json
import time
import argparse
import sys
from pathlib import Path

# Tentative d'import des outils du projet
try:
    from tools.hub_messenger import HubMessenger
    from tools.task_context import TaskContext
except ImportError:
    print("[!] Erreur : Dossier 'tools' ou fichiers requis introuvables.")
    sys.exit(1)

class HubTester:
    def __init__(self, user="test", password="test"):
        self.messenger = HubMessenger(user=user, password=password)
        self.all_results = []

    def _check_success(self, ctx, label):
        """Valide si le retour serveur correspond à l'attendu (label du JSON)"""
        cat_ok = ctx.category in label
        sub_ok = (ctx.sub_category in label) if ctx.sub_category != 'NONE' else True
        # res_ok = (ctx.result in label) if ctx.result != 'NONE' else True
        return cat_ok and sub_ok # and res_ok

    def _execute_group(self, group):
        """Exécute un groupe de commandes précis"""
        label = group.get('expected', 'Unknown')
        commands = group.get('ordre', [])
        group_contexts = []

        print(f"\n>>> GROUPE : {label}")
        
        for cmd in commands:
            clean_cmd = cmd.replace('test:', '')
            print(f"[*] Envoi : {clean_cmd[:40]:<40}", end="\r")
            
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
        """Mode interactif pour choisir son groupe (Scrappé du Fichier 1)"""
        while True:
            print(f"\n{'='*10} LISTE DES TESTS {'='*10}")
            for i, group in enumerate(test_groups, 1):
                print(f"[{i}] {group.get('expected', 'Unnamed')}")
            print(f"{'='*32}")
            
            choice = input('\nSélectionnez un numéro (ou [Q] pour quitter, [A] pour tout lancer) : ').strip().lower()

            if choice == 'q': break
            if choice == 'a':
                self.run_auto_mode(test_groups)
                break

            try:
                idx = int(choice) - 1
                if 0 <= idx < len(test_groups):
                    self.all_results = [] # Reset pour ce test précis
                    self._execute_group(test_groups[idx])
                    self._display_global_report()
                else:
                    print("[!] Index hors limites.")
            except ValueError:
                print("[!] Entrée invalide.")

    def run_auto_mode(self, test_groups):
        """Mode automatique : lance tout à la suite"""
        print(f"\n🚀 LANCEMENT AUTOMATIQUE ({len(test_groups)} groupes)")
        for group in test_groups:
            self._execute_group(group)
        self._display_global_report()

    def _display_global_report(self):
        """Rapport final formaté"""
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
            print(f"\n❌ ÉCHECS ({len(failed_list)}):")
            for label, ctx in failed_list:
                print(f"  - Attendu: {label} | Reçu: {ctx.category} {ctx.sub_category} (Query: {ctx.user_input})")

        rate = (total_success / total_queries * 100) if total_queries > 0 else 0
        print(f"\n{'='*60}")
        print(f"SCORE FINAL   : {total_success}/{total_queries} ({rate:.2f}%)")
        print(f"TEMPS TOTAL   : {total_time:.2f}s")
        print(f"{'='*60}\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=str, help="Fichier JSON de tests")
    parser.add_argument("-a", "--auto", action="store_true", help="Mode auto")
    parser.add_argument("--user", default="test")
    parser.add_argument("--passw", default="test")
    args = parser.parse_args()

    # Chargement du JSON
    p = Path(args.file)
    if not p.exists():
        print(f"Fichier non trouvé: {args.file}")
        sys.exit(1)
        
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tester = HubTester(user=args.user, password=args.passw)

    if args.auto:
        tester.run_auto_mode(data)
    else:
        tester.run_interactive_mode(data)